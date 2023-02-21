"""
Compiler layer for distributed processor. Program is input as a list of 
dicts encoding gates + branching operations. Each instruction dict has a 
'name' key followed by other instruction specific keys. 

TODO: add coredest to wiremap and parse this out in compiler

Instruction dict format:
    gate instructions: {'name': gatename, 'qubit': qubitid, 'modi': gate_param_mod_dict}
        gatename can be any named gate in the QChip object (qubitconfig.json), aside
        from names reserved for other operations described below. Named gate in QChip 
        object is gatename concatenated with qubitid (e.g. for the 'Q0read' gate you'd 
        use gatename='read' and qubitid='Q0'
    store fproc instruction:
        {'name': 'store_fproc', 'fproc_id': function_id, 'dest': var_name, 'scope': qubits}
        stores fproc result (next available from fproc_id) in variable var_name for use 
        later in the program.
    barrier: {'name': 'barrier', 'qubits': qubitid_list}
        reference all subsequent gates to a common start time after the barrier (set by 
        the latest gate/measurement on any qubit in qubitid_list)
    sync: {'name': 'sync', 'barrier_id': id, 'qubits': qubitid_list}
        synchronizes the gate time references between the cores corresponding to the qubits
        in qubitid_list.
    branch instructions: 
        branch on variable/measurement/fproc_id. General format is:
        {'alu_cond': <le or ge or eq>, 'cond_rhs': <reg or ival>, 'scope': <list_of_qubits> True: [instruction_list], False: [instruction_list]...}

        branch_fproc: {'name': 'branch_fproc', 'fproc_id': function_id, 'alu_cond': <alu_cond> ...}
        branch directly on latest (next available) fproc result.

        branch_var: {'name': 'branch_var', 'var': var_name, ...}
        branch on previously stored variable
    ALU instructions:
        {'name': 'alu', 'op': 'add' or 'sub' or 'le' or 'ge' or 'eq', 'in0': var_name, 'in1': var_name or value, 'out': output reg}
    variable declaration:
        {'name': declare, 'var': varname, 'dtype': int or phase or amp, 'scope': qubits}


    Note about instructions using function processor (FPROC): these instructions are scheduled
    immediately and use the next available function proc output. Which measurements are actually
    used for this depend on the configuration of the function processor. For flexibility, we don't 
    impose a particular configuration in this layer. It is the responsibilty of the programmer 
    to understand the configuration and schedule these instructions using appropriate delays, 
    etc as necessary.

    The measure/store instruction assumes an fproc_id mapping between qubits and raw measurements;
    this is not guaranteed to work across all FPROC implementations (TODO: maybe add software checks
    for this...)
"""

import numpy as np
import matplotlib.pyplot as plt
import os
import sys
import copy
try:
    import ipdb
except ImportError:
    print('warning: failed to import ipdb')
import json
from collections import OrderedDict

import qubitconfig.qchip as qc
import distproc.assembler as asm

RESRV_NAMES = ['branch_fproc', 'branch_var', 'barrier', 'delay', 'sync', 'virtualz', 'jump_i', 'alu', 'declare', 'jump_label']
INITIAL_TSTART = 5

class Compiler:
    """
    Class for compiling a quantum circuit encoded in the above format.
    Compilation stages:
        1. Determine the overall program scope (i.e. qubits used) as well
            as the scope of any declared variables
        2. Construct basic blocks -- these are sections of code with linear 
            control flow (no branching/jumping/looping). In general, basic 
            blocks are scoped to some subset of qubits.
        3. Determine the (per qubit) control flow graph which outlines
            the possible control flow paths between the different basic blocks
            (for that qubit/proc core)
        4. Schedule the gates within each basic block
        5. Schedule the full program
        6. Compile everything down to pulse level (CompiledProgram object)
    General usage:
        compiler = Compiler(...)
        compiler.schedule() # optional
        prog = compiler.compile()
    """
    def __init__(self, program, proc_groups, fpga_config, qchip):
        """
        Parameters
        ----------
            program : list of dicts
                program to compile, in QubiC circuit format
            proc_groups : str or list of tuples
                if list of tuples, indicates the channels controlled by each 
                core. e.g. [(Q0.qdrv, Q0.rdrv), (Q1.qdrv, Q1.rdrv)] indicates
                that two cores are used, one for Q0 rdrv/qdrv and another for Q1.
                if 'by_qubit', groups channels such that there is one core per
                qubit.
            fpga_config : distproc.hwconfig.FPGAConfig object
                specifies FPGA clock period and execution time for relevant
                instructions
            qchip : qubitconfig.qchip.QChip object
                qubit calibration configuration; specifies constituent pulses
                for each native gate
        """
        self._fpga_config = fpga_config

        self.qchip = qchip

        if isinstance(program, list):
            self._from_list(program)

        else:
            raise TypeError('program must be of type list')

        self._scope_program()
        self._lint_and_scopevars()

        if isinstance(proc_groups, list):
            self.proc_groups = proc_groups
        elif proc_groups == 'by_qubit':
            self.proc_groups = [('{}.qdrv'.format(q), '{}.rdrv'.format(q), '{}.rdlo'.format(q)) for q in self.qubits]
        elif proc_groups == 'by_channel':
            self.proc_groups = [('{}.qdrv'.format(q)) for q in self.qubits] 
            self.proc_groups.extend([('{}.rdrv'.format(q)) for q in self.qubits])
            self.proc_groups.extend([('{}.rdlo'.format(q)) for q in self.qubits])
        else:
            raise ValueError('{} group not supported'.format(proc_groups))

        self.zphase = {} #keys: Q0.freq, Q1.freq, etc; values: zphase
        self.chan_to_core = {} # maps qubit channels (e.g. Q0.qdrv) to core in asm dict
        for qubit in self.qubits:
            for chantype in ['qdrv', 'rdrv', 'rdlo']:
                chan = '{}.{}'.format(qubit, chantype)
                for grp in self.proc_groups:
                    if chan in grp:
                        self.chan_to_core[chan] = grp
                        break

            for freqname in qchip.qubit_dict[qubit].keys():
                self.zphase[qubit + '.' + freqname] = 0

        self._flat_program = self._flatten_control_flow(self._program)
        self._make_basic_blocks()
        self._generate_cfg()

        self.is_scheduled = False

    def _flatten_control_flow(self, program, label_prefix=''):
        flattened_program = []
        branchind = 0
        for i, statement in enumerate(program):
            statement = copy.deepcopy(statement)
            if statement['name'] in ['branch_fproc', 'branch_var']:
                falseblock = statement['false']
                trueblock = statement['true']

                jump_label_true = '{}true_{}'.format(label_prefix, branchind)
                jump_label_false = '{}false_{}'.format(label_prefix, branchind)
                jump_label_end = '{}end_{}'.format(label_prefix, branchind)

                statement['true'] = jump_label_true
                statement['false'] = jump_label_false

                # statement['jump_label'] = jump_label_true
                flattened_program.append(statement)
                flattened_falseblock = self._flatten_control_flow(falseblock, label_prefix='false_'+label_prefix)
                flattened_falseblock.insert(0, {'name': 'jump_label', 'label': jump_label_false, 'scope': statement['scope']})
                flattened_falseblock.append({'name': 'jump_i', 'jump_label': jump_label_end,
                                             'scope': statement['scope']})
                flattened_program.extend(flattened_falseblock)

                flattened_trueblock = self._flatten_control_flow(trueblock, label_prefix='true_'+label_prefix)
                flattened_trueblock.insert(0, {'name': 'jump_label', 'label': jump_label_true, 'scope': statement['scope']})
                flattened_program.extend(flattened_trueblock)
                flattened_program.append({'name': 'jump_label', 'label': jump_label_end, 'scope': statement['scope']})

                branchind += 1
            elif statement['name'] == 'alu_op':
                statement = statement.copy()
            else:
                flattened_program.append(statement)

        return flattened_program

    def _make_basic_blocks(self):
        self._basic_blocks = OrderedDict()
        cur_blockname = 'block_0'
        blockind = 1
        cur_block = []
        for statement in self._flat_program:
            if statement['name'] in ['branch_fproc', 'branch_var', 'jump_i']:
                self._basic_blocks[cur_blockname] = BasicBlock(cur_block, self._fpga_config, self.qchip)
                ctrl_blockname = '{}_ctrl'.format(cur_blockname)
                self._basic_blocks[ctrl_blockname] = BasicBlock([statement], self._fpga_config, self.qchip)
                cur_blockname = 'block_{}'.format(blockind)
                blockind += 1
                cur_block = []
            elif statement['name'] == 'jump_label':
                self._basic_blocks[cur_blockname] = BasicBlock(cur_block, self._fpga_config, self.qchip)
                cur_block = [statement]
                cur_blockname = statement['label']

            elif statement['name'] == 'for_loop':
                raise NotImplementedError
            else:
                cur_block.append(statement)

        self._basic_blocks[cur_blockname] = BasicBlock(cur_block, self._fpga_config, self.qchip)

        basic_blocks_nonempty = {}
        for blockname, block in self._basic_blocks.items():
            if not block.is_empty:
                basic_blocks_nonempty[blockname] = block

        self._basic_blocks = basic_blocks_nonempty
        self._basic_blocks['start'] = BasicBlock([], self._fpga_config, self.qchip)



    def _generate_cfg(self):
        self._control_flow_graph = {q: {'start': None} for q in self.qubits}
        qubit_lastblock = {q: 'start' for q in self.qubits}
        for blockname, block in self._basic_blocks.items():
            for qubit in self.qubits:
                if qubit in block.scope:
                    if qubit_lastblock[qubit] is not None:
                        self._control_flow_graph[qubit][qubit_lastblock[qubit]] = [blockname]

                    if block.dest_nodes is not None:
                        self._control_flow_graph[qubit][blockname] = block.dest_nodes
                        qubit_lastblock[qubit] = None
                    else:
                        qubit_lastblock[qubit] = blockname

        self._global_cfg = {}
        for qubit in self.qubits:
            for block, dest in self._control_flow_graph[qubit].items():
                if block in self._global_cfg.keys():
                    self._global_cfg[block].extend(dest.copy())
                else:
                    self._global_cfg[block] = dest.copy()
        
        for block, dest in self._global_cfg.items():
            #ipdb.set_trace()
            dest = list(set(dest))
                    

    def _get_cfg_predecessors(self):
        predecessors = {k: [] for k in self._basic_blocks.keys()}
        for node, dests in self._global_cfg.items():
            for dest in dests:
                predecessors[dest].append(node)

        return predecessors

    def schedule(self):
        block_start_time = {blockname: None for blockname, block in self._basic_blocks.items()}
        block_start_time['start'] = INITIAL_TSTART
        cfg_predecessors = self._get_cfg_predecessors()
        for _, block in self._basic_blocks.items():
            block.schedule()

        node_queue = self._global_cfg['start']
        while node_queue:
            ipdb.set_trace()
            cur_node = node_queue.pop(0)
            cur_node_predecessors = cfg_predecessors[cur_node]
            pred_block_start_times = [block_start_time[node] for node in cur_node_predecessors]
            if None not in pred_block_start_times:
                pred_block_dt = [block_start_time[node] 
                        + self._basic_blocks[node].delta_t for node in cur_node_predecessors]
                block_start_time[cur_node] = max(pred_block_dt)
                try:
                    node_queue.extend(self._global_cfg[cur_node])
                except KeyError:
                    pass
            else:
                node_queue.append(cur_node)

        self._block_start_time = block_start_time

        self.is_scheduled = True

    def _from_list(self, prog_list):
        self._program = prog_list

    def _scope_program(self):
        self.qubits = []
        for statement in self._program:
            if 'qubit' in statement.keys():
                self.qubits.extend(statement['qubit'])
            if 'scope' in statement.keys():
                self.qubits.extend(statement['scope'])
        self.qubits = list(np.unique(np.asarray(self.qubits)))

    def _lint_and_scopevars(self):
        vars = {}
        for statement in self._program:
            if 'qubit' in statement.keys():
                assert isinstance(statement['qubit'], list)
            else: # this is not a gate
                assert statement['name'] in RESRV_NAMES

            if statement['name'] == 'declare':
                assert statement['var'] not in vars.keys()
                vars[statement['var']] = {'dtype': statement['dtype'], 'scope': statement['scope']}
            elif statement['name'] == 'alu':
                assert vars[statement['in1']]['dtype'] == vars[statement['out']]['dtype']
                assert set(vars[statement['out']]['scope']).issubset(vars[statement['in1']]['scope'])
                if isinstance(statement['in0'], str):
                    assert statement['in0']['dtype'] == vars[statement['out']]['dtype']
                    assert set(vars[statement['out']]['scope']).issubset(vars[statement['in0']]['scope'])
                statement['scope'] = vars[statement['out']]['scope']

    def compile(self):
        if not self.is_scheduled:
            self.schedule()
            print('done scheduling')
        asm_progs = {grp: [{'op': 'phase_reset'}] for grp in self.proc_groups}
        for blockname, block in self._basic_blocks.items():
            compiled_block = block.compile(tstart=INITIAL_TSTART) # TODO: fix this so it's only on first block
            for proc_group in self.proc_groups:
                qubit = proc_group[0].split('.')[0]
                if qubit in compiled_block.keys():
                    asm_progs[proc_group].extend(compiled_block[qubit]) 

        for proc_group in self.proc_groups:
            asm_progs[proc_group].append({'op': 'done_stb'})

        return CompiledProgram(asm_progs, self._fpga_config)


class BasicBlock:
    """
    Class for representing "basic blocks" in a qubic program. Basic blocks are program segments
    with linear control flow; i.e. they consist only of gate/barrier sequences. Each basic block
    is scoped to some subset of qubits used by the circuit. This class has methods for scheduling gates
    within the basic block and determining the total delta t.

    TODO:
        maybe add stuff for modifying program?
            - gate parameters
            - contents

    methods:
        schedule

    attributes:
        program : high-level qubic program
        scheduled_program: program with added execution time in 't' key
        delta_t: total execution time of basic block, in fpga clocks
    """

    def __init__(self, program, fpga_config, qchip, swphase=True):
        self._program = program
        self._fpga_config = fpga_config
        self._scope()
        self.zphase = {}
        for qubit in self.scope:
            for freqname in qchip.qubit_dict[qubit].keys():
                self.zphase[qubit + '.' + freqname] = 0
        self.is_resolved = False
        self.is_scheduled = False
        self.is_zresolved = not swphase
        self._swphase = swphase
        self.qchip = qchip
        if not swphase:
            raise Exception('HW phases not yet implemented!')

    @property
    def dest_nodes(self):
        if self._program[-1]['name'] in ['branch_fproc', 'branch_var']:
            return [self._program[-1]['true'], self._program[-1]['false']]
        elif self._program[-1]['name'] in ['jump_i']:
            return [self._program[-1]['jump_label']]
        else:
            return None

    @property
    def is_empty(self):
        return len(self._program) == 0

    def _scope(self):
        self.scope = []
        for statement in self._program:
            if 'qubit' in statement.keys():
                self.scope.extend(statement['qubit'])
            elif 'scope' in statement.keys():
                self.scope.extend(statement['scope'])
        self.scope = list(np.unique(np.asarray(self.scope)))

    def schedule(self):
        if not self.is_resolved:
            self._resolve_gates()
            print('done resolving block')
        if not self.is_zresolved:
            self._resolve_virtualz_pulses()
            print('done z-resolving block')
        qubit_last_t = {q: 0 for q in self.scope}
        self.scheduled_program = []
        for gate in self.resolved_program:
            if isinstance(gate, dict):
                if gate['name'] == 'barrier':
                    qubit_max_t = max([qubit_last_t[qubit] for qubit in gate['qubit']])
                    for qubit in gate['qubit']:
                        qubit_last_t[qubit] = qubit_max_t
                elif gate['name'] == 'delay':
                    if 'qubit' not in gate:
                        gate['qubit'] = self.scope
                    elif isinstance(gate['qubit'], str):
                        gate['qubit'] = [gate['qubit']]
                    for qubit in gate['qubit']:
                        qubit_last_t[qubit] += self._get_pulse_nclks(gate['t'])
                elif gate['name'] == 'alu':
                    for qubit in self.scope:
                        qubit_last_t[qubit] += self._fpga_config.alu_instr_clks
                elif gate['name'] == 'branch_fproc':
                    for qubit in self.scope:
                        qubit_last_t[qubit] += self._fpga_config.jump_fproc_clks
                elif gate['name'] == 'jump_i':
                    for qubit in self.scope:
                        qubit_last_t[qubit] += self._fpga_config.jump_fproc_clks #todo: change to jump_i_clks
                elif gate['name'] == 'branch_var':
                    for qubit in self.scope:
                        qubit_last_t[qubit] += self._fpga_config.jump_cond_clks
                elif gate['name'] == 'jump_label':
                    pass
                else:
                    raise Exception('{} not yet implemented'.format(gate['name']))
                continue
            pulses = gate.get_pulses()
            min_pulse_t = []
            for pulse in pulses:
                qubit = pulse.dest[:2]
                assert qubit in self.scope
                qubit_t = qubit_last_t[qubit]
                min_pulse_t.append(qubit_t - self._get_pulse_nclks(pulse.t0))
            gate_t = max(min_pulse_t)
            for pulse in pulses:
                qubit_last_t[pulse.dest[:2]] = max(qubit_last_t[pulse.dest[:2]], gate_t \
                        + self._get_pulse_nclks(pulse.t0) + max(self._get_pulse_nclks(pulse.twidth),
                        self._fpga_config.pulse_regwrite_clks))

            self.scheduled_program.append({'gate': gate, 't': gate_t})
        try:
            self.delta_t = max(qubit_last_t.values())
        except ValueError:
            self.delta_t = 0
        self.is_scheduled = True

    def _resolve_gates(self):
        """
        convert gatedict references to objects, then dereference (i.e.
        all gate.contents elements are GatePulse objects)
        """
        self.resolved_program = []
        for gatedict in self._program:
            if gatedict['name'] in RESRV_NAMES:
                self.resolved_program.append(gatedict)
                continue
            if isinstance(gatedict['qubit'], str):
                gatedict['qubit'] = [gatedict['qubit']]
            gatename = ''.join(gatedict['qubit']) + gatedict['name']
            gate = self.qchip.gates[gatename]
            if 'modi' in gatedict and gatedict['modi'] is not None:
                gate = gate.get_updated_copy(gatedict['modi'])
            else:
                gate = gate.copy()
            gate.dereference()
            self.resolved_program.append(gate)
        self.is_resolved = True

    def _get_pulse_nclks(self, length_secs):
        return int(np.ceil(length_secs/self._fpga_config.fpga_clk_period))

    def _resolve_virtualz_pulses(self):
        zresolved_program = []
        for gate in self.resolved_program:
            if isinstance(gate, qc.Gate):
                # gate = gate.copy()
                for pulse in gate.contents:
                    # TODO: fix config/encoding of these
                    if pulse.is_zphase:
                        self.zphase[pulse.fcarriername] += pulse.pcarrier
                    else:
                        if pulse.fcarriername is not None:
                            # TODO: figure out if this is intended behavior...
                            pulse.pcarrier += self.zphase[pulse.fcarriername]
                gate.remove_virtualz()
                if len(gate.contents) > 0:
                    zresolved_program.append(gate)
            else:
                zresolved_program.append(gate)

        self.resolved_program = zresolved_program

    def compile(self, tstart=0):
        # TODO: add twidth attribute to env, not pulse
        compiled_program = {qubit: [] for qubit in self.scope}
        if not (self.is_resolved and self.is_scheduled):
            raise Exception('schedule and resolve gates first!')
        for i, instr in enumerate(self.scheduled_program):
            if 'gate' in instr.keys():
                for pulse in instr['gate'].get_pulses():
                    qubit_scope = pulse.dest.split('.')[0]
                    envdict = pulse.env.env_desc[0]
                    if 'twidth' not in envdict['paradict'].keys():
                        envdict['paradict']['twidth'] = pulse.twidth
                    start_time = instr['t'] + self._get_pulse_nclks(pulse.t0) + tstart
                    compiled_program[qubit_scope].append(
                            {'op': 'pulse', 'freq': pulse.fcarrier, 'phase': pulse.pcarrier, 'amp': pulse.amp,
                             'env': pulse.env.env_desc[0], 'start_time': start_time, 'dest': pulse.dest})
                    # lofreq = self.wiremap.lofreq[pulse.dest]
            elif instr['name'] == 'jump_label':
                self.scheduled_program[i + 1]['label'] = instr['label']
            else:
                raise Exception('{} not yet implemented'.format(instr['name']))
        return compiled_program

    def __repr__(self):
        return 'BasicBlock(' + str(self._program) + ')'


class CompiledProgram:
    """
    Simple class for reading/writing compiler output.

    Attributes:
        program : dict
            keys : proc group tuples (e.g. ('Q0.qdrv', 'Q0.rdrv', 'Q0.rdlo'))
            values : assembly program for corresponding proc core, in the format
                specified at the top of assembler.py. 

                NOTE: there is one deviation from this format; pulse commands 
                have a 'dest' field indicating the pulse channel, instead of
                an 'elem_ind'

        proc groups : list of proc group tuples

    TODO: metadata to consider adding:
        qchip version?
        git revision?
    """

    def __init__(self, program, fpga_config):
        self.fpga_config = fpga_config
        self.program = program

    @property
    def proc_groups(self):
        return self.program.keys()

    def save(self, filename):
        progdict = {'fpga_config': self.fpga_config.__dict__, **self.program}
        with open(filename) as f:
            json.dumps(progdict, f, indent=4)

    def load(self, filename):
        pass

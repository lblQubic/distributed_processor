"""
Compiler layer for distributed processor. Program is input as a list of 
dicts encoding gates and processor instructions. Each instruction dict has a 
'name' key followed by other instruction specific keys. 

Instruction dict format:
    gate instructions: 
        {'name': gatename, 'qubit': [qubitid], 'modi': gate_param_mod_dict, 'reg_param': (pulseind, attribute, name)}

        gatename can be any named gate in the QChip object (qubitconfig.json), aside
        from names reserved for other operations described below. Named gate in QChip 
        object is gatename concatenated with qubitid (e.g. for the 'Q0read' gate you'd 
        use gatename='read' and qubitid='Q0'). 'modi' and 'reg_param' are optional.

    pulse instructions:
        {'name': 'pulse', 'freq': <float or str> , 'phase': <float (radians)>, 'amp': <float>, 
         'twidth': <float>, 'env': <np.ndarray (samples) or dict>, 'dest': <str>}

        params is a dict of pulse parameters, formatted the same way as pulses in qubitcfg.json files 
        (or alternatively GatePulse object cfg_dicts)

    virtualz gates:
        {'name': 'virtualz', 'qubit': [qubitid], 'phase': phase_in_rad, 'freqname': freq_name}

        'freqname' is optional; default is 'freq', which gets resolved into '<qubitid>.<freqname>' from qchip.
        This generally corresponds to the qubit drive frequency in the qchip file. Other frequencies include 
        readfreq and freq_ef.

        'phase' is phase in radians

    frequency declaration:
        {'name': 'declare_freq', 'freq': freq_in_Hz, scope: <list_of_qubits_or_channels>, 'freq_ind': <hw_index>}

        Declares a frequency to be used by the specified qubits or channels. 'freq_ind' can subsequently be 
        referenced by a register (i.e. if 'reg_param' is set to parameterize a pulse frequency). If 'freq_ind' 
        is not set in the instruction, it is inferred implicitly by incrementing the previous freq_ind, starting from 
        0. Note that scheduling a gate/pulse with a previously unused frequency will implicitly cause it to
        be declared in the assembly program.

    z-phase parameterization:
        By default, all z-gates are implemented in software; all X90, etc pulse phases are set according to
        the preceding z-gates, and the z-gate instructions are removed from the program. However, this
        is not always possible when z-gates need to be applied conditionally. A z-phase can be bound
        to a processor register using the following instruction:

        {'name': 'bind_phase', 'freq': freq_name, 'var': reg_name}

        If this instruction is used, all z-gates applied to freq_name (frequency referenced in qchip;
        e.g. Q0.freq, Q1.readfreq, etc), are done in realtime on the processor, and all pulses using
        freq_name are phase parameterized by reg_name. reg_name must be declared separately.

        (this seems more like a compiler directive?)
        
    read fproc instruction:
        {'name': 'read_fproc', 'func_id': function_id, 'dest': var_name, 'scope': qubits}

        stores fproc result (next available from func_id) in variable var_name for use 
        later in the program.

    barrier: 
        {'name': 'barrier', 't': <delaytime in seconds> 'qubits': qubitid_list}

        add (software) delay between gates. 'qubits' is optional; if not specified assumed to be
        all qubits in the program

    delay: 
        {'name': 'delay', 'qubits': qubitid_list}

    sync: 
        {'name': 'sync', 'barrier_id': id, 'qubits': qubitid_list}

        synchronizes the gate time references between the cores corresponding to the qubits
        in qubitid_list.

    branch instructions: 
        {'name': 'branch_fproc', alu_cond: <'le' or 'ge' or 'eq'>, 'cond_lhs': <var or ival>, 
            'func_id': function_id, 'scope': <list_of_qubits> 'true': [instruction_list], 'false': [instruction_list]}
        branch directly on latest (next available) fproc result.

        {'name': 'branch_var', alu_cond: <'le' or 'ge' or 'eq'>, 'cond_lhs': <var or ival>, 
            'cond_rhs': var_name, 'scope': <list_of_qubits> 'true': [instruction_list], 'false': [instruction_list]}
        branch on variable

        {'name': 'loop', 'cond_lhs': <reg or ival>, 'cond_rhs': var_name, 'scope': <list_of_qubits>, 
            'body': [instruction_list]}
        repeats the instruction list 'body' when condition is true

    ALU instructions:
        {'name': 'alu', 'op': 'add' or 'sub' or 'le' or 'ge' or 'eq', 'lhs': var_name or value, 'rhs': var_name, 'out': output reg}

    variable declaration:
        {'name': declare, 'var': varname, 'dtype': int or phase or amp, 'scope': qubits}


    Note about instructions using function processor (FPROC): these instructions are scheduled
    immediately and use the next available function proc output. Which measurements are actually
    used for this depend on the configuration of the function processor. For flexibility, we don't 
    impose a particular configuration in this layer. It is the responsibilty of the programmer 
    to understand the configuration and schedule these instructions using appropriate delays, 
    etc as necessary.

    The measure/store instruction assumes an func_id mapping between qubits and raw measurements;
    this is not guaranteed to work across all FPROC implementations (TODO: maybe add software checks
    for this...)
"""

import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
import os
import sys
import copy
import logging 
import parse
import re
try:
    import ipdb
except ImportError:
    logging.warning('failed to import ipdb')
import json
from collections import OrderedDict

import qubitconfig.qchip as qc
import distproc.assembler as asm
import distproc.hwconfig as hw
import distproc.ir as ir

RESRV_NAMES = ['branch_fproc', 'branch_var', 'barrier', 'delay', 'sync', 
               'jump_i', 'alu', 'declare', 'jump_label', 'done',
               'jump_fproc', 'jump_cond', 'loop_end', 'loop']
INITIAL_TSTART = 5
DEFAULT_FREQNAME = 'freq'
PULSE_VALID_FIELDS = ['name', 'freq', 'phase', 'amp', 'twidth', 'env', 'dest']

def get_default_passes(fpga_config, qchip, qubit_grouping=('{qubit}.qdrv', '{qubit}.rdrv', '{qubit}.rdlo')):
    return [ir.ScopeProgram(qubit_grouping),
            ir.RegisterVarsAndFreqs(),
            ir.ResolveGates(qchip, qubit_grouping),
            ir.GenerateCFG(),
            ir.ResolveVirtualZ(),
            ir.ResolveFreqs(qchip),
            ir.Schedule(fpga_config)]

class Compiler:
    """
    Class for compiling a quantum circuit encoded in the above format.
    Compilation stages:
        1. Determine the overall program scope (i.e. qubits used) as well
            as the scope of any declared variables
        2. Convert program to intermediate representation: at the moment,
            this is just flattening the control flow heirarchy to jump statements
        3. Construct basic blocks -- these are sections of code with linear 
            control flow (no branching/jumping/looping). In general, basic 
            blocks are scoped to some subset of qubits.
        4. Determine the control flow graph which outlines
            the possible control flow paths between the different basic blocks
            (for that qubit/proc core)
        5. Schedule all pulses
        6. Compile everything down to pulse level (CompiledProgram object)
    General usage:
        compiler = Compiler(...)
        compiler.schedule() # optional
        prog = compiler.compile()
    """
    def __init__(self, program, proc_grouping=[('{qubit}.qdrv', '{qubit}.rdrv', '{qubit}.rdlo')]):
        """
        Parameters
        ----------
            program : list of dicts
                program to compile, in QubiC circuit format
            proc_grouping : str 
                if 'by_qubit', groups channels such that there is one core per
                qubit.
                if 'by_channel', groups channels such that there is one core per
                channel per qubit.
                if 'by_drive_ro', groups channels such that there is one core per
                drive channel per qubit, and another for both readout channels (per qubit)
            fpga_config : distproc.hwconfig.FPGAConfig object
                specifies FPGA clock period and execution time for relevant
                instructions
            qchip : qubitconfig.qchip.QChip object
                qubit calibration configuration; specifies constituent pulses
                for each native gate
        """
        processed_program = self._preprocess(program)
        self.ir_prog = ir.IRProgram(processed_program)
        self._proc_grouping = proc_grouping
        #self.proc_groups = set(generate_proc_groups(proc_grouping, self.qubits))

        #self.chan_to_core = {} # maps qubit channels (e.g. Q0.qdrv) to core in asm dict

        # for qubit in self.qubits:
        #     for chantype in ['qdrv', 'rdrv', 'rdlo']:
        #         chan = '{}.{}'.format(qubit, chantype)
        #         for grp in self.proc_groups:
        #             if chan in grp:
        #                 self.chan_to_core[chan] = grp
        #                 break

        #     for freqname in qchip.qubit_dict[qubit.split('.')[0]].keys():
        #         self.zphase[qubit + '.' + freqname] = 0


    def _preprocess(self, input_program):
        """
        flatten control flow and optionally lint
        """
        return generate_flat_ir(input_program)

    def run_ir_passes(self, passes):
        for ir_pass in passes:
            ir_pass.run_pass(self.ir_prog)

    def compile(self):
        self._core_scoper = _CoreScoper(self.ir_prog.scope, self._proc_grouping)
        asm_progs = {grp: [{'op': 'phase_reset'}] for grp in self._core_scoper.proc_groupings_flat}
        for blockname in self.ir_prog.blocknames_by_ind:
            self._compile_block(asm_progs, self.ir_prog.blocks[blockname]['instructions'])

        for proc_group in self._core_scoper.proc_groupings_flat:
            asm_progs[proc_group].append({'op': 'done_stb'})

        return CompiledProgram(asm_progs, self.ir_prog.fpga_config)

    def _compile_block(self, asm_progs, instructions):
        proc_groups_bydest = self._core_scoper.proc_groupings
        # TODO: add twidth attribute to env, not pulse
        for i, instr in enumerate(instructions):
            if instr.name == 'pulse':
                proc_group = proc_groups_bydest[instr.dest]

                if isinstance(instr.env, dict):
                    env = instr.env
                elif isinstance(instr.env[0], dict):
                    env = instr.env[0]
                    if len(instr.env) > 1:
                        logging.getLogger(__name__).warning(f'Only first env paradict {env} is being used')
                else:
                    env = instr.env

                if isinstance(env, dict):
                    if 'twidth' not in env['paradict'].keys():
                        env['paradict']['twidth'] = instr.twidth

                asm_progs[proc_group].append(
                        {'op': 'pulse', 'freq': instr.freq, 'phase': instr.phase, 'amp': instr.amp,
                         'env': env, 'start_time': instr.start_time, 'dest': instr.dest})

            elif instr.name == 'jump_label':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'jump_label', 'dest_label': instr.label})

            elif instr.name == 'declare':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'declare_reg', 'name': instr.var, 'dtype': instr.dtype})

            elif instr.name == 'alu':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'reg_alu', 'in0': instr.lhs, 'in1': instr.rhs, 
                                                      'alu_op': instr.alu_op, 'out_reg': instr.out})

            elif instr.name == 'jump_fproc':
                statement = {'op': 'jump_fproc', 'in0': instr.cond_lhs, 'alu_op': instr.alu_cond, 
                             'jump_label': instr.jump_label, 'func_id': instr.func_id}
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append(statement)

            elif instr.name == 'jump_cond':
                statement = {'op': 'jump_cond', 'in0': instr.cond_lhs, 'alu_op': instr.alu_cond, 
                             'jump_label': instr.jump_label, 'in1': instr.cond_rhs}
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append(statement)

            elif instr.name == 'jump_i':
                statement = {'op': 'jump_i', 'jump_label': instr.jump_label}
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append(statement)

            elif instr.name == 'loop_end':
                statement = {'op': 'inc_qclk', 'in0': -self.ir_prog.loops[instr.loop_label].delta_t}
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append(statement)

            else:
                raise Exception(f'{instr.name} not yet implemented')

    def __repr__(self):
        return 'BasicBlock(' + str(self._program) + ')'

    def _resolve_duplicate_jumps(self):
        #todo: write method to deal with multiple jump labels in a row
        pass


def generate_flat_ir(program, label_prefix=''):
    """
    Generates an intermediate representation with control flow resolved into simple 
    conditional jump statements. This function is recursive to allow for nested control 
    flow structures.

    instruction format is the same as compiler input, with the following modifications:

    branch instruction:
        {'name': 'branch_fproc', alu_cond: <'le' or 'ge' or 'eq'>, 'cond_lhs': <var or ival>, 
            'func_id': function_id, 'scope': <list_of_qubits> 'true': [instruction_list_true], 'false': [instruction_list_false]}
    becomes:
        {'name': 'jump_fproc', alu_cond: <'le' or 'ge' or 'eq'>, 'cond_lhs': <var or ival>, 
            'func_id': function_id, 'scope': <list_of_qubits> 'jump_label': <jump_label_true>}
        [instruction_list_false]
        {'name': 'jump_i', 'jump_label': <jump_label_end>}
        {'name': 'jump_label',  'label': <jump_label_true>}
        [instruction_list_true]
        {'name': 'jump_label',  'label': <jump_label_end>}

    for 'branch_var', 'jump_fproc' becomes 'jump_cond', and 'func_id' is replaced with 'cond_rhs'

    .....

    loop:
        {'name': 'loop', 'cond_lhs': <reg or ival>, 'cond_rhs': var_name, 'scope': <list_of_qubits>, 
            'alu_cond': <'le' or 'ge' or 'eq'>, 'body': [instruction_list]}

    becomes:
        {'name': 'jump_label', 'label': <loop_label>}
        {'name': 'barrier', 'scope': <list_of_qubits>}
        [instruction_list]
        {'name': 'loop_end', 'scope': <list_of_qubits>, 'loop_label': <loop_label>}
        {'name': 'jump_cond', 'cond_lhs': <reg or ival>, 'cond_rhs': var_name, 'scope': <list_of_qubits>,
         'jump_label': <loop_label>, 'jump_type': 'loopctrl'}
        

    TODO: consider sticking this in a class
    """
    flattened_program = []
    branchind = 0
    for i, statement in enumerate(program):
        statement = copy.deepcopy(statement)
        if statement['name'] in ['branch_fproc', 'branch_var']:
            falseblock = statement['false']
            trueblock = statement['true']

            flattened_trueblock = generate_flat_ir(trueblock, label_prefix='true_'+label_prefix)
            flattened_falseblock = generate_flat_ir(falseblock, label_prefix='false_'+label_prefix)

            jump_label_false = '{}false_{}'.format(label_prefix, branchind)
            jump_label_end = '{}end_{}'.format(label_prefix, branchind)

            if statement['name'] == 'branch_fproc':
                jump_statement = {'name': 'jump_fproc', 'alu_cond': statement['alu_cond'], 'cond_lhs': statement['cond_lhs'],
                                  'func_id': statement['func_id'], 'scope': statement['scope']}
            else:
                jump_statement = {'name': 'jump_cond', 'alu_cond': statement['alu_cond'], 'cond_lhs': statement['cond_lhs'],
                                  'cond_rhs': statement['cond_rhs'], 'scope': statement['scope']}

            if len(flattened_trueblock) > 0:
                jump_label_true = '{}true_{}'.format(label_prefix, branchind)
                jump_statement['jump_label'] = jump_label_true
            else:
                jump_statement['jump_label'] = jump_label_end

            flattened_program.append(jump_statement)

            flattened_falseblock.insert(0, {'name': 'jump_label', 'label': jump_label_false, 'scope': statement['scope']})
            flattened_falseblock.append({'name': 'jump_i', 'jump_label': jump_label_end,
                                         'scope': statement['scope']})
            flattened_program.extend(flattened_falseblock)

            if len(flattened_trueblock) > 0:
                flattened_trueblock.insert(0, {'name': 'jump_label', 'label': jump_label_true, 'scope': statement['scope']})
            flattened_program.extend(flattened_trueblock)
            flattened_program.append({'name': 'jump_label', 'label': jump_label_end, 'scope': statement['scope']})

            branchind += 1

        elif statement['name'] == 'loop':
            body = statement['body']
            flattened_body = generate_flat_ir(body, label_prefix='loop_body_'+label_prefix)
            loop_label = '{}loop_{}_loopctrl'.format(label_prefix, branchind)

            flattened_program.append({'name': 'jump_label', 'label': loop_label, 'scope': statement['scope']})
            flattened_program.append({'name': 'barrier', 'qubit': statement['scope']})
            flattened_program.extend(flattened_body)
            flattened_program.append({'name': 'loop_end', 'loop_label': loop_label, 'scope': statement['scope']})
            flattened_program.append({'name': 'jump_cond', 'cond_lhs': statement['cond_lhs'], 'cond_rhs': statement['cond_rhs'], 
                                      'alu_cond': statement['alu_cond'], 'jump_label': loop_label, 'scope': statement['scope'],
                                      'jump_type': 'loopctrl'})
            branchind += 1

        elif statement['name'] == 'alu_op':
            statement = statement.copy()

        else:
            flattened_program.append(statement)

    return flattened_program

class CompiledProgram:
    """
    Simple class for reading/writing compiler output.

    Attributes:
        program : dict
            keys : proc group tuples (e.g. ('Q0.qdrv', 'Q0.rdrv', 'Q0.rdlo'))
                this is a tuple of channels that are driven by that proc core
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

    def __init__(self, program, fpga_config=None):
        self.fpga_config = fpga_config
        self.program = program

    @property
    def proc_groups(self):
        return self.program.keys()

    def save(self, filename):
        progdict = copy.deepcopy(self.program)
        if self.fpga_config is not None:
            progdict['fpga_config'] = self.fpga_config.__dict__

        with open(filename) as f:
            json.dumps(progdict, f, indent=4)

    def load(self, filename):
        raise NotImplementedError()


def load_compiled_program(filename):
    with open(filename) as f:
        progdict = json.load(f)

    return hw.FPGAConfig(**progdict['fpga_config'])



class _CoreScoper:

    def __init__(self, qchip_or_dest_channels=None, proc_grouping=[('{qubit}.qdrv', '{qubit}.rdrv', '{qubit}.rdlo')]):
        if isinstance(qchip_or_dest_channels, qc.QChip):
            self._dest_channels = qchip_or_dest_channels.dest_channels
        else:
            self._dest_channels = qchip_or_dest_channels
        self._generate_proc_groups(proc_grouping)

        self.proc_groupings_flat = set(self.proc_groupings.values())

    def _generate_proc_groups(self, proc_grouping):
        proc_groupings = {}
        for dest in self._dest_channels:
            for group in proc_grouping:
                for dest_pattern in group:
                    sub_dict = parse.parse(dest_pattern, dest)
                    if sub_dict is not None:
                        proc_groupings[dest] = tuple(pattern.format(**sub_dict.named) for pattern in group)

        self.proc_groupings = proc_groupings

    def get_groups_bydest(self, dests):
        groups = set()
        for dest in dests:
            groups.add(self.proc_groupings[dest])

        return groups


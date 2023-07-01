from attrs import define, field
from collections import OrderedDict
import numpy as np
import copy
import networkx as nx
import parse
from abc import ABC, abstractmethod
import qubitconfig.qchip as qc
import logging
import distproc.hwconfig as hw
import distproc.ir_instructions as iri


@define
class _Frequency:
    freq: float
    zphase: float
    scope: set = None

@define
class _Variable:
    name: str
    scope: set
    dtype: str = 'int' # 'int', 'phase', or 'amp'

@define
class _Loop:
    name: str
    scope: set 
    start_time: int
    delta_t: int

class IRProgram:
    """
    Defines and stores an intermediate representation for qubic programs. All program 
    instructions are defined by one of the (public) classes in ir_instructions.py. 

    The program itself is stored in the control_flow_graph attribute, where each node is 
    a "basic block", defined to be a chunk of code with only linear control flow (i.e. all
    jumps, etc happen between blocks, not inside a block). The possible control flow paths
    through the program are specified as directed edges within this graph, and are determined
    during the GenerateCFG pass.

    In general, each node has the following attibutes:
        instructions: list containing the program instructions
        scope: set of channels involved with this block

        Other attributes can be added during various compiler passes

    Class attributes:
        freqs: dictionary of named freqs
        vars: dictionary of _Variable objects (mapped to proc core registers)
        loops: dictionary of named _Loop objects (stores start time and delta_t for scheduling)

        fpga_config: FPGAConfig object containing timing parameters used for scheduling. This is optional,
                as it is only used as metadata in the final compiled program.


    """

    def __init__(self, source):
        """
        Parameters
        ----------
            source: list of dicts
                
        """
        full_program = self._resolve_instr_objects(source)
        self._make_basic_blocks(full_program)
        self._freqs = {}
        self._vars = {}
        self.loops = {}
        self.fpga_config = None
    
    def _resolve_instr_objects(self, source):
        full_program = []
        for instr in source:
            instr_class = eval('iri.' + _get_instr_classname(instr['name']))
            full_program.append(instr_class(**instr))

        return full_program
    
    def _make_basic_blocks(self, full_program):
        """
        Splits the source into basic blocks; source order is preserved using the ind
        attribute in each node
        """
        self.control_flow_graph = nx.DiGraph()
        cur_blockname = 'block_0'
        blockname_ind = 1
        block_ind = 0
        cur_block = []
        for statement in full_program:
            if statement.name in ['jump_fproc', 'jump_cond', 'jump_i']:
                self.control_flow_graph.add_node(cur_blockname, instructions=cur_block, ind=block_ind)
                block_ind += 1
                if statement.jump_label.split('_')[-1] == 'loopctrl': #todo: break this out
                    ctrl_blockname = '{}_ctrl'.format(statement.jump_label)
                else:
                    ctrl_blockname = '{}_ctrl'.format(cur_blockname)
                self.control_flow_graph.add_node(ctrl_blockname, instructions=[statement], ind=block_ind)
                block_ind += 1
                cur_blockname = 'block_{}'.format(blockname_ind)
                blockname_ind += 1
                cur_block = []
            elif statement.name == 'jump_label':
                self.control_flow_graph.add_node(cur_blockname, instructions=cur_block, ind=block_ind)
                cur_block = [statement]
                cur_blockname = statement.label
            else:
                cur_block.append(statement)

        self.control_flow_graph.add_node(cur_blockname, instructions=cur_block, ind=block_ind)

        for node in tuple(self.control_flow_graph.nodes):
            if self.control_flow_graph.nodes[node]['instructions'] == []:
                self.control_flow_graph.remove_node(node)

    @property
    def blocks(self):
        return self.control_flow_graph.nodes

    @property
    def blocknames_by_ind(self):
        return sorted(self.control_flow_graph.nodes, key=lambda node: self.control_flow_graph.nodes[node]['ind'])

    @property
    def freqs(self):
        return self._freqs

    @property
    def vars(self):
        return self._vars

    @property
    def scope(self):
        return set().union(*list(self.control_flow_graph.nodes[node]['scope'] for node in self.blocks))

    def register_freq(self, key, freq):
        if key in self._freqs and self._freqs[key] != freq:
            raise Exception(f'frequency {key} already registered; provided freq {freq}\
                    does not match {self._freqs[key]}')
        self._freqs[key] = freq

    def register_var(self, varname, scope, dtype):
        if varname in self._vars.keys():
            raise Exception(f'Variable {varname} already declared!')
        self._vars[varname] = _Variable(varname, scope, dtype)

    def register_loop(self, name, scope, start_time, delta_t=None):
        self.loops[name] = _Loop(name, scope, start_time, delta_t)


def _get_instr_classname(name):
    classname = ''.join(word.capitalize() for word in name.split('_'))
    if name == 'virtualz':
        classname = 'VirtualZ'
        logging.getLogger(__name__).warning('Name virtualz is deprecated and will be removed \
                in a future version. Use \'virtual_z\' instead.')
    elif classname not in dir(iri):
        classname = 'Gate'
    return classname



class _QubitScoper:
    """
    Class for handling qubit -> scope/core mapping.
    "Scope" here refers to the set of channels a given pulse will affect (blcok)
    for scheduling and control flow purposes. For example, an X90 gate on Q1 will 
    be scoped to all channels Q1.*, since we don't want any other pulses playing on
    the other Q1 channels simultaneously. 
    """

    def __init__(self, mapping=('{qubit}.qdrv', '{qubit}.rdrv', '{qubit}.rdlo')):
        self._mapping = mapping

    def get_scope(self, qubits):
        if isinstance(qubits, str):
            qubits = [qubits]

        channels = ()
        for qubit in qubits:
            if any(parse.parse(chan_pattern, qubit) for chan_pattern in self._mapping):
                qubit_chans = (qubit,)
            else:
                qubit_chans = tuple(chan.format(qubit=qubit) for chan in self._mapping)
            channels += qubit_chans

        return set(channels)


"""
Passes go here. An abstract "Pass" class is used to make it easy to create parameterized
passes and give them to the compiler
"""
class Pass(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def run_pass(self, ir_prog: IRProgram):
        pass

class ScopeProgram(Pass):
    """
    Determines the scope of all blocks in the program graph. For instructions
    with a 'qubit' attribute, scope is determined using the 'qubit_grouping' 
    argument

    Modifications to IRProgram:
        - sets the "scope" attibute for all of the nodes
        - converts any qubits to lists of channels, store in scope attribute
          of instructions
    """

    def __init__(self, qubit_grouping: tuple, rescope_barriers_and_delays=True):
        """
        Parameters
        ----------
            qubit_grouping : tuple
                tuple of channels scoped to a qubit. Qubits are specified 
                using format strings with a 'qubit' attribute, for example:
                    ('{qubit}.qdrv', '{qubit}.rdrv', '{qubit}.rdlo')
                forms a valid qubit grouping of channels that will be scoped to 
                'qubit'
        """
        self._scoper = _QubitScoper(qubit_grouping) 
        self._rescope = rescope_barriers_and_delays

    def run_pass(self, ir_prog):
        for node in ir_prog.blocks:
            block = ir_prog.blocks[node]['instructions']
            scope = set()
            for instr in block:
                if hasattr(instr, 'scope') and instr.scope is not None:
                    instr_scope = self._scoper.get_scope(instr.scope)
                    instr.scope = instr_scope
                    scope = scope.union(instr_scope)
                elif hasattr(instr, 'qubit') and instr.qubit is not None:
                    instr_scope = self._scoper.get_scope(instr.qubit)
                    instr.scope = instr_scope
                    scope = scope.union(instr_scope)
                elif hasattr(instr, 'dest'):
                    scope = scope.union(self._scoper.get_scope(instr.dest))
    
            ir_prog.control_flow_graph.nodes[node]['scope'] = scope

        if self._rescope:
            self._rescope_barriers_and_delays(ir_prog)

    def _rescope_barriers_and_delays(self, ir_prog: IRProgram):
        for node in ir_prog.blocks:
            block = ir_prog.blocks[node]['instructions']
            for instr in block:
                if instr.name == 'barrier' or instr.name == 'delay':
                    if instr.scope is None:
                        instr.scope = ir_prog.scope

class RegisterVarsAndFreqs(Pass):
    """
    Register the (explicitly declared) frequencies and variables into the 
    ir program
    """

    def __init__(self):
        pass

    def run_pass(self, ir_prog: IRProgram):
        for node in ir_prog.blocks:
            for instr in ir_prog.blocks[node]['instructions']:
                if instr.name == 'declare_freq':
                    freqname = instr.freqname if instr.freqname is not None else instr.freq
                    ir_prog.register_freq(freqname, instr.freq)
                elif instr.name == 'declare':
                    ir_prog.register_var(instr.var, instr.scope, instr.dtype)

class ResolveGates(Pass):
    """
    Resolves all Gate objects into constituent pulses, as determined by the 
    provided qchip object. 

    Modifications to IRProgram:
        - convert Gate objects to:
            Barrier(scope of gate)
            Pulse0
            Pulse1,
            etc
    """
    def __init__(self, qchip, qubit_grouping):
        self._qchip = qchip
        self._scoper = _QubitScoper(qubit_grouping)
    
    def run_pass(self, ir_prog: IRProgram):
        for node in ir_prog.blocks:
            block = ir_prog.blocks[node]['instructions']

            i = 0
            while i < len(block):
                if isinstance(block[i], iri.Gate):
                    # remove gate instruction from block and decrement index
                    instr = block.pop(i)

                    gate = self._qchip.gates[''.join(instr.qubit) + instr.name]
                    if instr.modi is not None:
                        gate = gate.get_updated_copy(instr.modi)
                    gate.dereference()

                    pulses = gate.get_pulses()

                    block.insert(i, iri.Barrier(scope=self._scoper.get_scope(instr.qubit)))
                    i += 1

                    for pulse in pulses:
                        if isinstance(pulse, qc.GatePulse):
                            if pulse.freqname is not None:
                                if pulse.freqname not in ir_prog.freqs.keys():
                                    ir_prog.register_freq(pulse.freqname, pulse.freq)
                                elif pulse.freq != ir_prog.freqs[pulse.freqname]:
                                    logging.getLogger(__name__).warning(f'{pulse.freqname} = {ir_prog.freqs[pulse.freqname]}\
                                                                        differs from qchip value: {pulse.freq}')
                                freq = pulse.freqname
                            else:
                                if pulse.freq not in ir_prog.freqs.keys():
                                    ir_prog.register_freq(pulse.freq, pulse.freq)
                                freq = pulse.freq
                            if pulse.t0 != 0:
                                # TODO: figure out how to resolve these t0s...
                                block.insert(i, iri.Delay(t=pulse.t0, scope={pulse.dest}))
                                i += 1

                            block.insert(i, iri.Pulse(freq=freq, phase=pulse.phase, amp=pulse.amp, env=pulse.env,
                                                  twidth=pulse.twidth, dest=pulse.dest))
                            i += 1

                        elif isinstance(pulse, qc.VirtualZ):
                            block.insert(i, iri.VirtualZ(freq=pulse.global_freqname, phase=pulse.phase))
                            i += 1

                        else:
                            raise TypeError(f'invalid type {type(pulse)}')
                else:
                    i += 1 

class GenerateCFG(Pass):
    """
    Generate the control flow graph. Specifically, add directed edges between basic blocks
    encoded in ir_prog.control_flow_graph. Conditional jumps associated with loops are NOT
    included.
    """

    def __init__(self):
        pass

    def run_pass(self, ir_prog: IRProgram):
        lastblock = {dest: None for dest in ir_prog.scope}
        for blockname in ir_prog.blocknames_by_ind:
            block = ir_prog.blocks[blockname]
            for dest in block['scope']:
                if lastblock[dest] is not None:
                    ir_prog.control_flow_graph.add_edge(lastblock[dest], blockname)

            if block['instructions'][-1].name in ['jump_fproc', 'jump_cond']:
                if block['instructions'][-1].jump_type != 'loopctrl': 
                    # we want to keep this a DAG, so exclude loops and treat them separately for scheduling
                    ir_prog.control_flow_graph.add_edge(blockname, block['instructions'][-1].jump_label)
                for dest in block['scope']:
                    lastblock[dest] = blockname
            elif block['instructions'][-1].name == 'jump_i':
                ir_prog.control_flow_graph.add_edge(blockname, block['instructions'][-1].jump_label)
                for dest in block['scope']:
                    lastblock[dest] = None
            else:
                for dest in block['scope']:
                    lastblock[dest] = blockname

class ResolveHWVirtualZ(Pass):
    """
    Apply BindPhase instructions:
        - turn all VirtualZ instructions into register operations
        - if force=True, force all pulse phases using this frequency 
          to that register
    Run this BEFORE ResolveVirtualZ
    """
    pass

class ResolveVirtualZ(Pass):
    """
    For software VirtualZ (default) only. Resolve VirtualZ gates into
    hardcoded phase offsets

    Requirements:
        - all blocks (and relevant instructions) are scoped
            e.g. ScopeProgram
        - all gates are resolved
        - control flow graph is generated
    """

    def __init__(self):
        pass

    def run_pass(self, ir_prog: IRProgram):
        for nodename in nx.topological_sort(ir_prog.control_flow_graph):
            zphase_acc = {}
            for pred_node in ir_prog.control_flow_graph.predecessors(nodename):
                for freqname, phase in ir_prog.blocks[pred_node]['ending_zphases'].items():
                    if freqname in zphase_acc.keys():
                        if phase != zphase_acc[freqname]:
                            raise ValueError(f'Phase mismatch in {freqname} at {nodename} predecessor {pred_node}\
                                    ({phase} rad)')
                    else:
                        zphase_acc[freqname] = phase

            instructions = ir_prog.blocks[nodename]['instructions']
            i = 0
            while i < len(instructions):
                instr = instructions[i]
                if isinstance(instr, iri.Pulse):
                    if instr.freq in zphase_acc.keys():
                        instr.phase += zphase_acc[instr.freq]
                elif isinstance(instr, iri.VirtualZ):
                    instructions.pop(i)
                    i -= 1
                    if instr.freq in zphase_acc.keys():
                        zphase_acc[instr.freq] += instr.phase
                    else: 
                        zphase_acc[instr.freq] = instr.phase
                elif isinstance(instr, iri.Gate):
                    raise Exception('Must resolve Gates first!')
                elif isinstance(instr, iri.JumpCond) and instr.jump_type == 'loopctrl':
                    logging.getLogger(__name__).warning('Z-phase resolution inside loops not supported, be careful!')
                i += 1

            ir_prog.blocks[nodename]['ending_zphases'] = zphase_acc
                
class ResolveFreqs(Pass):

    def __init__(self, qchip: qc.QChip = None):
        self._qchip = qchip

    def run_pass(self, ir_prog: IRProgram):

        for nodename in nx.topological_sort(ir_prog.control_flow_graph):
            instructions = ir_prog.blocks[nodename]['instructions']

            for instr in instructions:
                if instr.name == 'pulse':
                    if isinstance(instr.freq, str):
                        if instr.freq in ir_prog.vars.keys():
                            #this is a var parameterized freq
                            assert instr.dest in ir_prog.vars[instr.freq].scope
                        elif instr.freq in ir_prog.freqs:
                            instr.freq = ir_prog.freqs[instr.freq]
                        else:
                            instr.freq = self._qchip.get_qubit_freq(instr.freq)
                            

class Schedule(Pass):

    def __init__(self, fpga_config: hw.FPGAConfig):
        self._fpga_config = fpga_config
        self._start_nclks = 5

    def run_pass(self, ir_prog: IRProgram):
        # TODO: add loopdict checking
        for nodename in nx.topological_sort(ir_prog.control_flow_graph):
            cur_t = {dest: self._start_nclks for dest in ir_prog.blocks[nodename]['scope']}
            for pred_node in ir_prog.control_flow_graph.predecessors(nodename):
                for dest in cur_t.keys():
                    if dest in ir_prog.blocks[pred_node]['scope']:
                        cur_t[dest] = max(cur_t[dest], ir_prog.blocks[pred_node]['block_end_t'][dest])


            if self._check_nodename_loopstart(nodename):
                ir_prog.register_loop(nodename, ir_prog.blocks[nodename]['scope'],
                                      max(cur_t.values()))

            self._schedule_block(ir_prog.blocks[nodename]['instructions'], cur_t)

            if isinstance(ir_prog.blocks[nodename]['instructions'][-1], iri.JumpCond) \
                    and ir_prog.blocks[nodename]['instructions'][-1].jump_type == 'loopctrl':
                loopname = ir_prog.blocks[nodename]['instructions'][-1].jump_label
                ir_prog.blocks[nodename]['block_end_t'] = {dest: ir_prog.loops[loopname].start_time \
                        for dest in ir_prog.blocks[nodename]['scope']}
                ir_prog.loops[loopname].delta_t = max(cur_t.values()) - ir_prog.loops[loopname].start_time

            else:
                ir_prog.blocks[nodename]['block_end_t'] = cur_t

        ir_prog.fpga_config = self._fpga_config


    def _schedule_block(self, instructions, cur_t):
        i = 0
        while i < len(instructions):
            instr = instructions[i]
            if instr.name == 'pulse':
                instr.start_time = cur_t[instr.dest]
                cur_t[instr.dest] += self._get_pulse_nclks(instr.twidth)
            elif instr.name == 'barrier':
                max_t = max(cur_t[dest] for dest in instr.scope)
                for dest in instr.scope:
                    cur_t[dest] = max_t
                instructions.pop(i)
                i -= 1
            elif instr.name == 'delay':
                for dest in instr.scope:
                    cur_t[dest] += self._get_pulse_nclks(instr.t)
                instructions.pop(i)
                i -= 1

            # TODO: this is very conservative scheduling; some of this time can be 
            #   absorbed by pulse execution
            elif instr.name == 'alu':
                for dest in instr.scope:
                    cur_t[dest] += self._fpga_config.alu_instr_clks
            elif instr.name == 'jump_fproc':
                for dest in instr.scope:
                    cur_t[dest] += self._fpga_config.jump_fproc_clks
            elif instr.name == 'jump_i':
                for dest in instr.scope:
                    cur_t[dest] += self._fpga_config.jump_cond_clks
            elif instr.name == 'jump_cond':
                for dest in instr.scope:
                    cur_t[dest] += self._fpga_config.jump_cond_clks
            elif instr.name == 'loop_end':
                for dest in instr.scope:
                    cur_t[dest] += self._fpga_config.alu_instr_clks
            elif isinstance(instr, iri.Gate):
                raise Exception('Must resolve gates first!')

            i += 1

    def _get_pulse_nclks(self, length_secs):
        return int(np.ceil(length_secs/self._fpga_config.fpga_clk_period))


    def _check_nodename_loopstart(self, nodename):
        return nodename.split('_')[-1] == 'loopctrl'


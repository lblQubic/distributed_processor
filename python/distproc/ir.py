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

@define
class Gate:
    name: str
    _qubit: list | str
    modi: dict = None
    start_time: int = None

    @property
    def qubit(self):
        if isinstance(self._qubit, list):
            return self._qubit
        elif isinstance(self._qubit, str):
            return [self._qubit]
        else:
            raise TypeError

@define
class Pulse:
    name: str = 'pulse'
    freq: str | float
    phase: str | float
    amp: str | float
    twidth: float
    env: np.ndarray | dict
    dest: str
    start_time: int = None

@define
class VirtualZ:
    name: str = 'virtualz'
    _qubit: str = None
    _freq: str | float = 'freq'
    phase: float

    @property
    def freq(self):
        if isinstance(self._freq, str):
            if self.qubit is not None:
                return ''.join(self.qubit) + f'.{self._freq}'
            else:
                return self._freq

        else:
            return self._freq

    @property
    def qubit(self):
        if isinstance(self._qubit, list):
            return self._qubit
        elif isinstance(self._qubit, str):
            return [self._qubit]
        else:
            raise TypeError


@define
class DeclareFreq:
    name: str = 'declare_freq'
    freqname: str = None
    freq: float
    scope: list
    freq_ind: int = None

@define
class Barrier:
    name: str = 'barrier'
    qubits: list = None
    scope: list | tuple | set = None

@define
class Delay:
    name: str = 'delay'
    qubits: list = None
    scope: list | tuple | set = None
    t: float

@define
class JumpFproc:
    name: str = 'jump_fproc'
    alu_cond: str
    cond_lhs: int | str
    func_id: int
    scope: list
    jump_label: str

@define
class ReadFproc:
    name: str = 'read_fproc'
    alu_cond: str
    cond_lhs: int | str
    func_id: int
    scope: list | set
    jump_label: str

@define
class JumpLabel:
    name: str = 'jump_label'
    jump_label: str

@define 
class JumpCond:
    name: str = 'jump_cond'
    cond_lhs: int | str
    cond_rhs: str
    scope: list | set
    jump_label: str
    jump_type: str = None

@define
class JumpI:
    name: str = 'jump_i'
    scope: list | set
    jump_label: str
    jump_type: str = None

@define
class Declare:
    name: str = 'declare'
    scope: list | set
    var: str
    dtype: str = 'int' # 'int', 'phase', or 'amp'

@define
class _Frequency:
    freq: float
    zphase: float
    scope: set = None

@define
class _Variable:
    name: str
    scope: set = None
    dtype: str # 'int', 'phase', or 'amp'


class IRProgram:

    def __init__(self, source):
        """
        Parameters
        ----------
            List of dicts in IR format
        """
        full_program = self._resolve_instr_objects(source)
        self._make_basic_blocks(full_program)
        self._freqs = {}
        self._vars = {}
    
    def _resolve_instr_objects(self, source):
        full_program = []
        for instr in source:
            instr_class = eval(_get_instr_classname(instr['name']))
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
                self.control_flow_graph.add_node(cur_blockname, instructions=[cur_block], ind=block_ind)
                cur_block = [statement]
                cur_blockname = statement.label
            else:
                cur_block.append(statement)

        self.control_flow_graph.add_node(cur_blockname, instructions=[cur_block], ind=block_ind)

        for node in self.control_flow_graph.nodes:
            if self.control_flow_graph.nodes[node]['instructions'] == []:
                self.control_flow_graph.remove_nodes(node)

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
        return set().union(self.control_flow_graph.nodes[node]['scope'] for node in self.blocks)

    def register_freq(self, key, freq):
        if key in self._freqs and self._freqs[key] != freq:
            raise Exception(f'frequency {key} already registered; provided freq {freq}\
                    does not match {self._freqs[key]}')
        self._freqs[key] = freq

    def register_var(self, varname, scope, dtype):
        if varname in self._vars.keys():
            raise Exception(f'Variable {varname} already declared!')
        self._vars[varname] = _Variable(varname, scope, dtype)


def _get_instr_classname(name):
    return ''.join(word.capitalize for word in name.split('_'))



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
    """

    def __init__(self, qubit_grouping: tuple):
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

    def run_pass(self, ir_prog):
        for node in ir_prog.blocks:
            block = ir_prog.blocks[node]['instructions']
            scope = set()
            for instr in block:
                if hasattr(instr, 'scope'):
                    scope.add(self._scoper.get_scope(instr.scope))
                elif hasattr(instr, 'qubit'):
                    instr_scope = self._scoper.get_scope(instr.qubit)
                    instr.scope = instr_scope
                    scope.add(instr_scope)
                elif hasattr(instr, 'dest'):
                    scope.add(self._scoper.get_scope(instr.dest))
    
            ir_prog.control_flow_graph.nodes[node]['scope'] = scope

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
    """
    def __init__(self, qchip, qubit_grouping):
        self._qchip = qchip
        self._scoper = _QubitScoper(qubit_grouping)
    
    def run_pass(self, ir_prog: IRProgram):
        for node in ir_prog.blocks:
            block = ir_prog.blocks[node]['instructions']

            i = 0
            while i < len(block):
                if isinstance(block[i], Gate):
                    # remove gate instruction from block and decrement index
                    instr = block.pop(i)
                    i -= 1

                    gate = self._qchip.gates[''.join(instr.qubit) + instr.name]
                    if instr.modi is not None:
                        gate = gate.get_updated_copy(instr.modi)
                    gate.dereference()

                    pulses = gate.get_pulses()

                    block.insert(i, Barrier(scope=self._scoper.get_scope(instr.qubit)))
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
                                block.insert(i, Delay(t=pulse.t0, scope={pulse.dest}))
                                i += 1

                            block.insert(i, Pulse(freq=freq, phase=pulse.phase, amp=pulse.amp, env=pulse.env,
                                                  twidth=pulse.twidth, dest=pulse.dest))
                            i += 1

                        elif isinstance(pulse, qc.VirtualZ):
                            block.insert(i, VirtualZ(freq=pulse.global_freqname, phase=pulse.phase))
                            i += 1

                        else:
                            raise TypeError(f'invalid type {type(pulse)}')

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
                    lastblock[dest] = block
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
    """

    def __init__(self):
        pass

    def run_pass(self, ir_prog: IRProgram):
        for nodename in nx.topological_sort(ir_prog.control_flow_graph):
            zphase_acc = {}
            for pred_node in ir_prog.control_flow_graph.predecessors(nodename):
                for freqname, phase in ir_prog.blocks[pred_node]['ending_zphases']:
                    if freqname in zphase_acc.keys():
                        if phase != zphase_acc[freqname]:
                            raise ValueError(f'Phase mismatch in {freqname} at {nodename} predecessor {pred_node}\
                                    ({phase} rad)')
                    else:
                        zphase_acc[freqname] = phase

            for instr in ir_prog.blocks[nodename]['instructions']:
                if isinstance(instr, Pulse):
                    if instr.freq in zphase_acc.keys():
                        instr.phase += zphase_acc
                elif isinstance(instr, VirtualZ):
                    zphase_acc[instr.freq] += instr.phase
                elif isinstance(instr, Gate):
                    raise Exception('Must resolve Gates first!')
                elif isinstance(instr, JumpCond) and instr.jump_type == 'loopctrl':
                    logging.getLogger(__name__).warning('Z-phase resolution inside loops not supported, be careful!')

            ir_prog.blocks[nodename]['ending_zphases'] = zphase_acc
                

class Schedule(Pass):

    def __init__(self, fpga_config: hw.FPGAConfig):
        self._fpga_config = fpga_config
        self._start_nclks = 5

    def run_pass(self, ir_prog: IRProgram):
        for nodename in nx.topological_sort(ir_prog.control_flow_graph):
            start_t = {dest: self._start_nclks for dest in ir_prog.blocks[nodename]['scope']}
            for pred_node in ir_prog.control_flow_graph.predecessors(nodename):
                for dest in start_t.keys():
                    if dest in ir_prog.blocks[pred_node]['scope']:
                        start_t[dest] = max(start_t, ir_prog.blocks[pred_node]['block_end_t'][dest])

            cur_t = copy.copy(start_t)

            self._schedule_block(ir_prog.blocks[nodename]['instructions'], cur_t)

            if self._check_nodename_loopstart(nodename):
                ir_prog.blocks[nodename]['block_end_t'] = start_t
            else:
                ir_prog.blocks[nodename]['block_end_t'] = cur_t

    def _schedule_block(self, instructions, cur_t):
        for instr in instructions:
            if instr.name == 'pulse':
                instr.start_time = cur_t[instr.dest]
                cur_t[instr.dest] += self._get_pulse_nclks(instr.twidth)
            elif instr.name == 'barrier':
                max_t = max(cur_t[dest] for dest in instr.scope)
                for dest in instr.scope:
                    cur_t = max_t
            elif instr.name == 'delay':
                for dest in instr.scope:
                    cur_t += self._get_pulse_nclks(instr.t)

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

    def _get_pulse_nclks(self, length_secs):
        return int(np.ceil(length_secs/self._fpga_config.fpga_clk_period))


    def _check_nodename_loopstart(self, nodename):
        return nodename.split('_')[-1] == 'loopctrl'


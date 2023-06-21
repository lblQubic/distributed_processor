from attrs import define, field
from collections import OrderedDict
import numpy as np
import networkx as nx
import parse
from abc import ABC, abstractmethod
import qubitconfig.qchip as qc

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
    phase: float
    amp: float
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
    freq: float
    scope: list
    freq_ind: int 

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

class JumpI:
    name: str = 'jump_i'
    scope: list | set
    jump_label: str
    jump_type: str = None

class _Frequency:
    freq: float
    zphase: float
    scope: set = None

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
                if statement['jump_label'].split('_')[-1] == 'loopctrl': #todo: break this out
                    ctrl_blockname = '{}_ctrl'.format(statement['jump_label'])
                else:
                    ctrl_blockname = '{}_ctrl'.format(cur_blockname)
                self.control_flow_graph.add_node(ctrl_blockname, instructions=[statement], ind=block_ind)
                block_ind += 1
                cur_blockname = 'block_{}'.format(blockname_ind)
                blockname_ind += 1
                cur_block = []
            elif statement['name'] == 'jump_label':
                self.control_flow_graph.add_node(cur_blockname, instructions=[cur_block], ind=block_ind)
                cur_block = [statement]
                cur_blockname = statement['label']
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
    def scope(self):
        return set().union(self.control_flow_graph.nodes[node]['scope'] for node in self.blocks)

    def register_freq(self, key, freq):
        if key in self._freqs and self._freqs[key] != freq:
            raise Exception(f'frequency {key} already registered; provided freq {freq}\
                    does not match {self._freqs[key]}')
        self._freqs[key] = freq


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
                    scope.add(self._scoper.get_scope(instr.qubit))
                elif hasattr(instr, 'dest'):
                    scope.add(self._scoper.get_scope(instr.dest))
    
            ir_prog.control_flow_graph.nodes[node]['scope'] = scope

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

class ResolveVirtualZ(Pass):
    pass

class Schedule(Pass):

    def __init__(self):
        pass

    def run_pass(self, ir_prog: IRProgram):
        pass


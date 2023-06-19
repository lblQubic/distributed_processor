from attrs import define, field
from collections import OrderedDict
import numpy as np
import networkx as nx
import parse
from abc import ABC, abstractmethod

@define
class Gate:
    name: str
    qubit: list
    modi: dict = None
    start_time: int = None

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
    qubit: str = None
    freq: str | float = 'freq'

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
    scope: list
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
    scope: list
    jump_label: str
    jump_type: str = None


class IRProgram:

    def __init__(self, source):
        """
        Parameters
        ----------
            List of dicts in IR format
        """
        full_program = self._resolve_instr_objects(source)
        self._make_basic_blocks(full_program)
    
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
    def run_pass(self, ir_prog):
        pass

class ScopeProgram(Pass):
    def __init__(self, qubit_grouping: tuple):
        self._scoper = _QubitScoper(qubit_grouping) 

    def run_pass(self, ir_prog):
        for node in ir_prog.control_flow_graph.nodes:
            block = ir_prog.control_flow_graph.nodes[node]['instructions']
            scope = set()
            for instr in block:
                if hasattr(instr, 'scope'):
                    scope.add(self._scoper.get_scope(instr.scope))
                elif hasattr(instr, 'qubit'):
                    scope.add(self._scoper.get_scope(instr.qubit))
                elif hasattr(instr, 'dest'):
                    scope.add(self._scoper.get_scope(instr.dest))
    
            ir_prog.control_flow_graph.nodes[node]['scope'] = scope

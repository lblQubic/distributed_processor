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

    def __init__(self, source: list):
        """
        Parameters
        ----------
            source: list of dicts or IR instructions
                If list of dicts, statements are immediately converted into IR instruction 
                objects, as defined in distproc.ir_instructions

        Control flow graph is initialized as a single node containing all statements. Flattening the control flow 
        heirarchy, generating basic blocks, and forming the CFG edges are done as separate passes
                
        """
        if isinstance(source[0], dict):
            source = _resolve_instr_objects(source)
        self.control_flow_graph = nx.DiGraph()
        self.control_flow_graph.add_node('block_0', instructions=source, ind=0)
        self._freqs = {}
        self._vars = {}
        self.loops = {}
        self.fpga_config = None
    
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

def _resolve_instr_objects(source: list[dict]):
    full_program = []
    for instr in source:
        instr_class = eval('iri.' + _get_instr_classname(instr['name']))
        if instr['name'] == 'virtualz':
            instr['name'] = 'virtual_z'

        instr_obj = instr_class(**instr)

        if 'true' in instr.keys():
            instr_obj.true = _resolve_instr_objects(instr['true'])
        if 'false' in instr.keys():
            instr_obj.false = _resolve_instr_objects(instr['false'])
        if 'body' in instr.keys():
            instr_obj.body = _resolve_instr_objects(instr['body'])

        full_program.append(instr_obj)

    return full_program


def _get_instr_classname(name):
    classname = ''.join(word.capitalize() for word in name.split('_'))
    if name == 'virtualz':
        classname = 'VirtualZ'
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

class FlattenProgram(Pass):
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
    """

    def __init__(self):
        pass

    def run_pass(self, ir_prog: IRProgram):
        assert len(ir_prog.control_flow_graph.nodes) == 1
        blockname = list(ir_prog.control_flow_graph.nodes)[0]
        instructions = ir_prog.control_flow_graph.nodes[blockname]['instructions']

        ir_prog.control_flow_graph.nodes[blockname]['instructions'] = self._flatten_control_flow(instructions)

    def _flatten_control_flow(self, program, label_prefix=''):
        flattened_program = []
        branchind = 0
        for i, statement in enumerate(program):
            statement = copy.deepcopy(statement)
            if statement.name in ['branch_fproc', 'branch_var']:
                falseblock = statement.false
                trueblock = statement.true
    
                flattened_trueblock = self._flatten_control_flow(trueblock, label_prefix='true_'+label_prefix)
                flattened_falseblock = self._flatten_control_flow(falseblock, label_prefix='false_'+label_prefix)
    
                jump_label_false = '{}false_{}'.format(label_prefix, branchind)
                jump_label_end = '{}end_{}'.format(label_prefix, branchind)
    
                if statement.name == 'branch_fproc':
                    jump_statement = iri.JumpFproc(alu_cond=statement.alu_cond, cond_lhs=statement.cond_lhs, 
                                                   func_id=statement.func_id, scope=statement.scope, jump_label=None)
                else:
                    jump_statement = iri.JumpCond(alu_cond=statement.alu_cond, cond_lhs=statement.cond_lhs, 
                                                   cond_rhs=statement.cond_rhs, scope=statement.scope, jump_label=None)

    
                if len(flattened_trueblock) > 0:
                    jump_label_true = '{}true_{}'.format(label_prefix, branchind)
                    jump_statement.jump_label = jump_label_true
                else:
                    jump_statement.jump_label = jump_label_end
    
                flattened_program.append(jump_statement)
    
                flattened_falseblock.insert(0, iri.JumpLabel(label=jump_label_false, scope=statement.scope))
                flattened_falseblock.append(iri.JumpI(jump_label=jump_label_end, scope=statement.scope))
                flattened_program.extend(flattened_falseblock)
    
                if len(flattened_trueblock) > 0:
                    flattened_trueblock.insert(0, iri.JumpLabel(label=jump_label_true, scope=statement.scope))
                flattened_program.extend(flattened_trueblock)
                flattened_program.append(iri.JumpLabel(label=jump_label_end, scope=statement.scope))
    
                branchind += 1
    
            elif statement.name == 'loop':
                body = statement.body
                flattened_body = self._flatten_control_flow(body, label_prefix='loop_body_'+label_prefix)
                loop_label = '{}loop_{}_loopctrl'.format(label_prefix, branchind)
    
                flattened_program.append(iri.JumpLabel(label=loop_label, scope=statement.scope))
                flattened_program.append(iri.Barrier(qubit=statement.scope))
                flattened_program.extend(flattened_body)
                flattened_program.append(iri.LoopEnd(loop_label=loop_label, scope=statement.scope))
                flattened_program.append(iri.JumpCond(cond_lhs=statement.cond_lhs, cond_rhs=statement.cond_rhs, 
                                          alu_cond=statement.alu_cond, jump_label=loop_label, scope=statement.scope,
                                          jump_type='loopctrl'))
                branchind += 1
    
            elif statement.name == 'alu_op':
                statement = statement.copy()
    
            else:
                flattened_program.append(statement)
    
        return flattened_program


class MakeBasicBlocks(Pass):
    """
    Makes basic blocks out of a flattened IR program. FlattenProgram pass MUST be run first 
    (i.e. no branch_x statements allowed, only jumps)
    """
    def __init__(self):
        pass

    def run_pass(self, ir_prog: IRProgram):
        """
        Splits the source into basic blocks; source order is preserved using the ind
        attribute in each node
        """
        assert len(ir_prog.control_flow_graph.nodes) == 1

        # assume whole program is in first (and only) node, break it out
        cur_blockname = list(ir_prog.control_flow_graph.nodes)[0]
        full_program = ir_prog.control_flow_graph.nodes[cur_blockname]['instructions']
        ir_prog.control_flow_graph.nodes[cur_blockname]['instructions'] = []

        blockname_ind = 1
        block_ind = 0
        cur_block = []

        for statement in full_program:
            if statement.name in ['jump_fproc', 'jump_cond', 'jump_i']:
                ir_prog.control_flow_graph.add_node(cur_blockname, instructions=cur_block, ind=block_ind)
                block_ind += 1
                if statement.jump_label.split('_')[-1] == 'loopctrl': #todo: break this out
                    ctrl_blockname = '{}_ctrl'.format(statement.jump_label)
                else:
                    ctrl_blockname = '{}_ctrl'.format(cur_blockname)
                ir_prog.control_flow_graph.add_node(ctrl_blockname, instructions=[statement], ind=block_ind)
                block_ind += 1
                cur_blockname = 'block_{}'.format(blockname_ind)
                blockname_ind += 1
                cur_block = []
            elif statement.name == 'jump_label':
                ir_prog.control_flow_graph.add_node(cur_blockname, instructions=cur_block, ind=block_ind)
                cur_block = [statement]
                cur_blockname = statement.label
            else:
                cur_block.append(statement)

        ir_prog.control_flow_graph.add_node(cur_blockname, instructions=cur_block, ind=block_ind)

        for node in tuple(ir_prog.control_flow_graph.nodes):
            if ir_prog.control_flow_graph.nodes[node]['instructions'] == []:
                ir_prog.control_flow_graph.remove_node(node)


class ScopeProgram(Pass):
    """
    Determines the scope of all basic blocks in the program graph. For instructions
    with a 'qubit' attribute, scope is determined using the 'qubit_grouping' 
    argument

    Changes:
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
                if instr.name == 'barrier' or instr.name == 'delay' or instr.name == 'idle':
                    if instr.scope is None:
                        instr.scope = ir_prog.scope

class RegisterVarsAndFreqs(Pass):
    """
    Register frequencies and variables into the ir program. Both explicitly 
    declared frequencies and Pulse instruction frequencies are registered. If
    a qchip is provided, Pulse instruction frequencies can be referenced to any
    qchip freq.

    Note that frequencies used/defined in Gate instructions are NOT registered here
    but are registered in the ResolveGates pass.

    Also scopes ALU instructions that use vars (todo: consider breaking this out), 
    according to the declared scope of input/output variables.
    """

    def __init__(self, qchip: qc.QChip = None):
        self._qchip = qchip

    def run_pass(self, ir_prog: IRProgram):
        for node in ir_prog.blocks:
            for instr in ir_prog.blocks[node]['instructions']:
                if instr.name == 'declare_freq':
                    freqname = instr.freqname if instr.freqname is not None else instr.freq
                    ir_prog.register_freq(freqname, instr.freq)
                elif instr.name == 'declare':
                    ir_prog.register_var(instr.var, instr.scope, instr.dtype)
                elif instr.name == 'pulse':
                    if instr.freq not in ir_prog.freqs.keys():
                        if isinstance(instr.freq, str):
                            if self._qchip is None:
                                raise Exception(f'Undefined reference to freq {instr.freq}; no QChip\
                                        object provided')
                            ir_prog.register_freq(instr.freq, self._qchip.get_qubit_freq(instr.freq))
                        else:
                            ir_prog.register_freq(instr.freq, instr.freq)

                elif instr.name == 'alu':
                    if isinstance(instr.lhs, str):
                        instr.scope = ir_prog.vars[instr.rhs].scope.union(ir_prog.vars[instr.lhs].scope)
                    else:
                        instr.scope = ir_prog.vars[instr.rhs].scope
                    assert ir_prog.vars[instr.out].scope.issubset(instr.scope)

                elif instr.name == 'set_var' or instr.name == 'read_fproc':
                    instr.scope = ir_prog.vars[instr.var].scope

                elif instr.name == 'alu_fproc':
                    if isinstance(instr.lhs, str):
                        instr.scope = ir_prog.vars[instr.rhs].scope



class ResolveGates(Pass):
    """
    Resolves all Gate objects into constituent pulses, as determined by the 
    provided qchip object. 

    Changes:
        - convert Gate objects to:
            Barrier(scope of gate)
            Pulse0,
            Pulse1,
            Delay,
            etc
        - named frequencies (e.g. freq: 'Q2.freq') are registered into ir_prog.freqs
          according to the qchip object (e.g. ir_prog.freqs['Q2.freq'] = 4.322352e9), 
          and the 'freq' attribute of the resulting pulse preserves the name.
        - numerical freqs are registered in the same way
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
    Apply BindPhase instructions and resolve hardware (runtime) virtual-z gates.

    Changes:
        - turn all VirtualZ instructions into register operations
        - initialize bound vars to 0 (i.e. add SetVar instructions)
        - force all pulse phases using the bound frequency 
          to that register

    Run this BEFORE ResolveVirtualZ
    """
    def __init__(self):
        pass

    def run_pass(self, ir_prog: IRProgram):
        hw_zphase_bindings = {} #keyed by freqname, value is varname
        for nodename in nx.topological_sort(ir_prog.control_flow_graph):
            instructions = ir_prog.blocks[nodename]['instructions']
            i = 0
            while i < len(instructions):
                instr = instructions[i]
                if instr.name == 'bind_phase':
                    assert instr.var in ir_prog.vars.keys()
                    hw_zphase_bindings[instr.freq] = instr.var
                    instructions.pop(i)
                    instructions.insert(i, iri.SetVar(value=0, var=instr.var, scope=ir_prog.vars[instr.var].scope))

                elif isinstance(instr, iri.VirtualZ):
                    if instr.freq in hw_zphase_bindings.keys():
                        if instr.scope is not None:
                            assert set(instr.scope).issubset(ir_prog.vars[hw_zphase_bindings[instr.freq]].scope)
                        alu_zgate = iri.Alu(op='add', lhs=instr.phase, rhs=hw_zphase_bindings[instr.freq],
                                            out=hw_zphase_bindings[instr.freq], scope=ir_prog.vars[hw_zphase_bindings[instr.freq]].scope)
                        instructions.pop(i)
                        instructions.insert(i, alu_zgate)
                
                elif instr.name == 'pulse':
                    if instr.freq in hw_zphase_bindings.keys():
                        instr.phase = hw_zphase_bindings[instr.freq]
                        assert instr.dest in ir_prog.vars[hw_zphase_bindings[instr.freq]].scope

                elif isinstance(instr, iri.Gate):
                    raise Exception(f'{iri.Gate.name} Gate found. All Gate instructions must be resolved before running this pass!')

                i += 1


class ResolveVirtualZ(Pass):
    """
    For software VirtualZ (default) only. Resolve VirtualZ gates into
    hardcoded phase offsets. If there are any conditional VirtualZ gates, 
    Z-gates on that phase MUST be encoded as registers in hardware
    (using BindPhase). This pass will check for z-phase consistency between
    predecessor nodes in the CFG.

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
                    if instr.freq not in ir_prog.freqs.keys():
                        logging.getLogger(__name__).warning(f'performing virtualz on unused frequency: {instr.freq}')
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
    """
    Resolve references to named frequencies. i.e. if pulse.freq is a string,
    assign it to the frequency registered in the IR program during the gate resolution
    and/or freq/var registration passes.
    """

    def __init__(self):
        pass

    def run_pass(self, ir_prog: IRProgram):

        for nodename in nx.topological_sort(ir_prog.control_flow_graph):
            instructions = ir_prog.blocks[nodename]['instructions']

            for instr in instructions:
                if instr.name == 'pulse':
                    if isinstance(instr.freq, str):
                        if instr.freq in ir_prog.vars.keys():
                            #this is a var parameterized freq
                            assert instr.dest in ir_prog.vars[instr.freq].scope
                        else:
                            instr.freq = ir_prog.freqs[instr.freq]

class ResolveFPROCChannels(Pass):
    """
    Resolve references to named FPROC channels according to the numerical ID
    or HW channel names given in fpga_config.fproc_config

    Changes:
        - func_id attributes get lowered according to fpga_config.fproc_config
        - Hold instructions are inserted to ensure that <Read, Jump, Alu>Fproc
          instruction is executed after the most recent measurement on the given
          channel is completed
    """
    
    def __init__(self, fpga_config: hw.FPGAConfig):
        self._fpga_config = fpga_config

    def run_pass(self, ir_prog: IRProgram):
        for nodename in nx.topological_sort(ir_prog.control_flow_graph):
            instructions = ir_prog.blocks[nodename]['instructions']

            i = 0
            while i < len(instructions):
                instr = instructions[i]
                if isinstance(instr, iri.ReadFproc) or isinstance(instr, iri.JumpFproc) \
                        or isinstance(instr, iri.AluFproc):
                    #instructions.insert(i, iri.Barrier(scope=instr.scope))
                    #i += 1
                    if instr.func_id in self._fpga_config.fproc_channels.keys():
                        fproc_chan = self._fpga_config.fproc_channels[instr.func_id]
                        instructions.insert(i, iri.Hold(fproc_chan.hold_nclks, ref_chans=fproc_chan.hold_after_chans, 
                                                        scope=instr.scope))
                        i += 1
                        instr.func_id = fproc_chan.id
                    else:
                        assert isinstance(instr.func_id, int)

                i += 1


                            
class Schedule(Pass):
    """
    Schedule all timed instructions. This includes Pulse and Hold/Idle instructions. Takes 
    into account branching/control flow, as well as the execution time of untimed (normal)
    instructions.

    Changes:
        - Hold instructions get resolved into Idle, with 't' attribute 
        - Delay and Barrier instructions are resolved and removed
        - Pulse instructions get assigned a 't' in units FPGA clocks
        - Loop execution time is determined so the appropriate IncQclk
          instructions can be added during compilation

    """

    def __init__(self, fpga_config: hw.FPGAConfig, proc_grouping: list):
        self._fpga_config = fpga_config
        self._start_nclks = 5
        self._proc_grouping = proc_grouping

    def run_pass(self, ir_prog: IRProgram):
        # TODO: add loopdict checking
        self._core_scoper = CoreScoper(ir_prog.scope, self._proc_grouping)
        for nodename in nx.topological_sort(ir_prog.control_flow_graph):
            cur_t_global = {dest: self._start_nclks for dest in ir_prog.scope}
            last_instr_end_t = {grp: self._start_nclks \
                    for grp in self._core_scoper.get_groups_bydest(ir_prog.blocks[nodename]['scope'])}

            for pred_node in ir_prog.control_flow_graph.predecessors(nodename):
                for dest in cur_t_global.keys():
                    if dest in ir_prog.blocks[pred_node]['scope']:
                        cur_t_global[dest] = max(cur_t_global[dest], ir_prog.blocks[pred_node]['block_end_t'][dest])
                for grp in last_instr_end_t:
                    if grp in ir_prog.blocks[pred_node]['last_instr_end_t']:
                        last_instr_end_t[grp] = max(last_instr_end_t[grp], ir_prog.blocks[pred_node]['last_instr_end_t'][grp])


            cur_t_local = {dest: cur_t_global[dest] for dest in cur_t_global.keys()}
            if self._check_nodename_loopstart(nodename):
                ir_prog.register_loop(nodename, ir_prog.blocks[nodename]['scope'],
                                      max(cur_t_local.values()))

            self._schedule_block(ir_prog.blocks[nodename]['instructions'], cur_t_global, last_instr_end_t)
            cur_t_local = {dest: cur_t_global[dest] for dest in cur_t_global.keys()}

            if isinstance(ir_prog.blocks[nodename]['instructions'][-1], iri.JumpCond) \
                    and ir_prog.blocks[nodename]['instructions'][-1].jump_type == 'loopctrl':
                loopname = ir_prog.blocks[nodename]['instructions'][-1].jump_label
                ir_prog.blocks[nodename]['block_end_t'] = {dest: ir_prog.loops[loopname].start_time \
                        for dest in ir_prog.blocks[nodename]['scope']}
                ir_prog.blocks[nodename]['last_instr_end_t'] = {grp: ir_prog.loops[loopname].start_time \
                        for grp in self._core_scoper.get_groups_bydest(ir_prog.blocks[nodename]['scope'])}
                ir_prog.loops[loopname].delta_t = max(max(last_instr_end_t.values()), max(cur_t_local.values())) \
                        - ir_prog.loops[loopname].start_time

            else:
                ir_prog.blocks[nodename]['block_end_t'] = cur_t_local
                ir_prog.blocks[nodename]['last_instr_end_t'] = last_instr_end_t

        ir_prog.fpga_config = self._fpga_config


    def _schedule_block(self, instructions, cur_t, last_instr_end_t):
        i = 0
        while i < len(instructions):
            instr = instructions[i]
            if instr.name == 'pulse':
                last_instr_t = last_instr_end_t[self._core_scoper.proc_groupings[instr.dest]]
                instr.start_time = max(last_instr_t, cur_t[instr.dest])

                last_instr_end_t[self._core_scoper.proc_groupings[instr.dest]] = instr.start_time \
                        + self._fpga_config.pulse_load_clks
                cur_t[instr.dest] = instr.start_time + self._get_pulse_nclks(instr.twidth)

            elif instr.name == 'barrier':
                max_cur_t = max(cur_t[dest] for dest in instr.scope)
                max_last_instr_t = max(last_instr_end_t[self._core_scoper.proc_groupings[dest]] for dest in instr.scope)
                max_t = max(max_cur_t, max_last_instr_t)
                for dest in instr.scope:
                    cur_t[dest] = max_t
                instructions.pop(i)
                i -= 1

            elif instr.name == 'delay':
                for dest in instr.scope:
                    cur_t[dest] += self._get_pulse_nclks(instr.t)
                instructions.pop(i)
                i -= 1

            elif instr.name == 'alu' or instr.name == 'set_var':
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    last_instr_end_t[grp] += self._fpga_config.alu_instr_clks

            elif instr.name in ['jump_fproc', 'read_fproc', 'alu_fproc']:
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    last_instr_end_t[grp] += self._fpga_config.jump_fproc_clks

            elif instr.name == 'jump_i':
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    last_instr_end_t[grp] += self._fpga_config.jump_cond_clks

            elif instr.name == 'jump_cond':
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    last_instr_end_t[grp] += self._fpga_config.jump_cond_clks

            elif instr.name == 'loop_end':
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    last_instr_end_t[grp] += self._fpga_config.alu_instr_clks

            elif instr.name == 'hold':
                max_t = max(cur_t[dest] for dest in instr.ref_chans)
                idle_end_t = max_t + instr.nclks
                idle_instr_scope = set()
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    if last_instr_end_t[grp] >= idle_end_t:
                        logging.getLogger(__name__).info(f'skipping hold on core {grp}, idle timestamp exceeded')
                    else:
                        idle_instr_scope = idle_instr_scope.union(grp)
                        last_instr_end_t[grp] = idle_end_t + self._fpga_config.pulse_load_clks

                if len(idle_instr_scope) > 0:
                    instructions[i] = iri.Idle(idle_end_t, scope=idle_instr_scope)
                else:
                    instructions.pop(i)
                    i -= 1

            elif isinstance(instr, iri.Gate):
                raise Exception('Must resolve gates first!')

            i += 1

    def _get_pulse_nclks(self, length_secs):
        return int(np.ceil(length_secs/self._fpga_config.fpga_clk_period))


    def _check_nodename_loopstart(self, nodename):
        return nodename.split('_')[-1] == 'loopctrl'


class LintSchedule(Pass):
    """
    Pass for checking that all timed instructions have been scheduled appropriately to
    avoid execution stalling. Does NOT check for sequence correctness; i.e. a new pulse can
    interrupt a previous pulse on the same channel.
    """
    def __init__(self, fpga_config: hw.FPGAConfig, proc_grouping: list):
        self._fpga_config = fpga_config
        self._start_nclks = 5
        self._proc_grouping = proc_grouping

    def run_pass(self, ir_prog: IRProgram):
        self._core_scoper = CoreScoper(ir_prog.scope, self._proc_grouping)
        for nodename in nx.topological_sort(ir_prog.control_flow_graph):
            last_instr_end_t = {grp: self._start_nclks \
                    for grp in self._core_scoper.get_groups_bydest(ir_prog.blocks[nodename]['scope'])}

            for pred_node in ir_prog.control_flow_graph.predecessors(nodename):
                for grp in last_instr_end_t:
                    if grp in ir_prog.blocks[pred_node]['last_instr_end_t']:
                        last_instr_end_t[grp] = max(last_instr_end_t[grp], ir_prog.blocks[pred_node]['last_instr_end_t'][grp])


            self._lint_block(ir_prog.blocks[nodename]['instructions'], last_instr_end_t)

            if isinstance(ir_prog.blocks[nodename]['instructions'][-1], iri.JumpCond) \
                    and ir_prog.blocks[nodename]['instructions'][-1].jump_type == 'loopctrl':
                loopname = ir_prog.blocks[nodename]['instructions'][-1].jump_label
                ir_prog.blocks[nodename]['last_instr_end_t'] = {grp: ir_prog.loops[loopname].start_time \
                        for grp in self._core_scoper.get_groups_bydest(ir_prog.blocks[nodename]['scope'])}

            else:
                ir_prog.blocks[nodename]['last_instr_end_t'] = last_instr_end_t

        ir_prog.fpga_config = self._fpga_config

    def _lint_block(self, instructions, last_instr_end_t):
        i = 0
        while i < len(instructions):
            instr = instructions[i]
            if instr.name == 'pulse':
                last_instr_t = last_instr_end_t[self._core_scoper.proc_groupings[instr.dest]]
                if instr.start_time < last_instr_t:
                    raise Exception(f'instruction: {instr} start time too early; must be >= {last_instr_t}')

                last_instr_end_t[self._core_scoper.proc_groupings[instr.dest]] = instr.start_time \
                        + self._fpga_config.pulse_load_clks

            elif instr.name == 'alu' or instr.name == 'set_var':
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    last_instr_end_t[grp] += self._fpga_config.alu_instr_clks

            elif instr.name in ['jump_fproc', 'read_fproc', 'alu_fproc']:
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    last_instr_end_t[grp] += self._fpga_config.jump_fproc_clks

            elif instr.name == 'jump_i':
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    last_instr_end_t[grp] += self._fpga_config.jump_cond_clks

            elif instr.name == 'jump_cond':
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    last_instr_end_t[grp] += self._fpga_config.jump_cond_clks

            elif instr.name == 'loop_end':
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    last_instr_end_t[grp] += self._fpga_config.alu_instr_clks

            elif instr.name == 'idle':
                for grp in self._core_scoper.get_groups_bydest(instr.scope):
                    if instr.end_time < last_instr_end_t[grp]:
                        raise Exception(f'instruction: {instr} end time too early; must be >= {last_instr_end_t[grp]}')
                    last_instr_end_t[grp] = instr.end_time + self._fpga_config.pulse_load_clks

            elif isinstance(instr, iri.Gate):
                raise Exception('Must resolve gates first!')

            i += 1


class CoreScoper:
    """
    Class for grouping firmware output channels into distributed processor cores. Processor cores are named using
    a tuple of channels controlled by that core (e.g. (Q0.qdrv, Q0.rdrv, Q0.rdlo))
    """

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
        """
        Given a set of destination channels, returns a set of tuples indicating the processor cores used to 
        control those channels

        Parameters
        ----------
            dests: set
                set of firmware output channels (e.g. {'Q0.qdrv', 'Q1.rdlo'})
        Returns
        -------
            set
                set of tuples that index all of the proc cores needed to control all of the channels in 'dests'
        """
        groups = set()
        for dest in dests:
            groups.add(self.proc_groupings[dest])

        return groups

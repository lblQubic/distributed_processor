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
    measure/store instruction: 
        {'name': 'measure', 'qubit': qubitid, 'modi': gate_param_mod_dict, 'dest': var_name}
        can store measurement result in named variable var_name, to be used for branching, etc,
        later on. Optional 'scope' key to specify qubits using the variable. Otherwise, scope
        is determined automatically by compiler.
    store fproc instruction:
        {'name': 'store_fproc', 'fproc_id': function_id, 'dest': var_name}
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
        {value0: [instruction_list], value1: [instruction_list]...}

        branch_fproc: {'name': 'branch_fproc', 'fproc_id': function_id, value0: ...}
        branch directly on latest (next available) fprc result.

        branch_var: {'name': 'branch_var', 'var': var_name, ...}
        branch on previously stored variable
    ALU instructions:
        {'name': 'add' or 'sub' or 'le' or 'ge' or 'eq', 'in0': var_name, 'in1': var_name or value}


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

import qubitconfig as qc
import assembler as asm

RESRV_NAMES = ['branch_fproc', 'branch_var', 'barrier', 'delay', 'sync']

class Compiler:
    def __init__(self, qubits, wiremap, qchip):
        self.qubits = qubits
        self.wiremap = wiremap
        self.qchip = qchip
        self._program = []
        self._isscheduled = False

        self.assemblers = {}
        for qubit in qubits:
            for chan, ind in wiremap.coredict.items():
                if qubit in chan:
                    self.assemblers[ind] = asm.SingleUnitAssembler()

    def add_statement(self, statement_dict, index=-1):
        if index==-1:
            self._program.append(statement_dict)
        else:
            self._program.insert(index, statement_dict)
        self._isscheduled = False

    def schedule(self):
        qubit_t = {q: 0 for q in self.qubits}
        core_t = {coreind: 0 for coreind in self.assemblers.keys()}
        for statement in self._program:
            if statement['name'] in RESERV_NAMES:
                raise Exception('only gates implemented so far')
            else:
                if isinstance(statement['qubit'], str):
                    gatename = statement['qubit'] + statement['name']
                elif isinstance(statement['qubit'], list):
                    gatename = ''.join(statement['qubit']) + statement['name']
                else:
                    raise TypeError('unsupported type')
                #TODO: apply gate mods here?
                gate = self.qchip.gates[gatename].get_updated_copy(statement['modi'])
                pulses = gate.get_pulses()

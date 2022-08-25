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
"""

import numpy as np
import matplotlib.pyplot as plt
import os
import sys

import qubitconfig as qc
import assembler as asm

RESRV_NAMES = ['br_fproc']

class Compiler:
    def __init__(self, qubits, wiremap, qchip):
        self.qubits = qubits
        self.wiremap = wiremap
        self.qchip = qchip
        self._program = []
        self._isscheduled = False

        self.assemblers = {}
        for qubit in qubits:
            self.assemblers[qubit] = asm.SingleUnitAssembler()

    def add_statement(self, statement_dict, index=-1):
        if index==-1:
            self._program.append(statement_dict)
        else:
            self._program.insert(index, statement_dict)
        self._isscheduled = False

    def schedule(self):
        qubit_t = {q: 0 for q in self.qubits}
        for statement in self._program:
            if statement['name'] in RESERV_NAMES:
                raise Exception('only gates implemented so far')
            if isinstance(statement['qubit'], str):
                gatename = statement['qubit']
            elif isinstance(statement['qubit'], list):
                gatename = ''.join(statement['qubit'])

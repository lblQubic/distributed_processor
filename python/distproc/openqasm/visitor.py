from openqasm3.visitor import QASMVisitor, QASMNode
import openqasm3.ast as ast
from distproc.openqasm.qubit_map import QubitMap, DefaultQubitMap
from distproc.openqasm.gate_map import GateMap, DefaultGateMap
import ipdb

class QASMQubiCVisitor(QASMVisitor):

    def __init__(self, qubit_map: QubitMap = DefaultQubitMap(), gate_map: GateMap = DefaultGateMap()):
        self.qubit_map = qubit_map
        self.gate_map = gate_map
        self.program = []
        super().__init__()

    def visit_QubitDeclaration(self, node: QASMNode):
        print("hello i am a qubit")
        #ipdb.set_trace()

    def visit_QuantumGate(self, node: QASMNode):
        print("hello i am a gate")
        gatename = node.name.name
        qubits = []
        for qubit_identifier in node.qubits:
            if isinstance(qubit_identifier, ast.Identifier):
                qubits.append(self.qubit_map.get_hardware_qubit(qubit_identifier.name))
            elif isinstance(qubit_identifier, ast.IndexedIdentifier):
                qubits.append(self.qubit_map.get_hardware_qubit(qubit_identifier.name.name, 
                                                                qubit_identifier.indices[0][0].value))
            else:
                raise Exception()
        
        self.program.append(self.gate_map.get_qubic_gateinstr(gatename, qubits))


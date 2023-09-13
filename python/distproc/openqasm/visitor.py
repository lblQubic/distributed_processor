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

        self.qubits = {}
        super().__init__()

    def visit_QubitDeclaration(self, node: QASMNode):
        print(f"hello i am a qubit: {node.qubit.name}")
        if node.size is not None:
            self.qubits[node.qubit.name] = node.size.value
        else:
            self.qubits[node.qubit.name] = None


    def visit_QuantumGate(self, node: QASMNode):
        gatename = node.name.name
        print(f"hello i am a {gatename}")
        qubits = []
        for qubit_identifier in node.qubits:
            if isinstance(qubit_identifier, ast.Identifier):
                assert self.qubits[qubit_identifier] is None # single qubit, has no size/wasn't declared as array
                qubits.append(self.qubit_map.get_hardware_qubit(qubit_identifier.name))
            elif isinstance(qubit_identifier, ast.IndexedIdentifier):
                qubits.append(self.qubit_map.get_hardware_qubit(qubit_identifier.name.name, 
                                                                qubit_identifier.indices[0][0].value))
            else:
                raise Exception()
        
        self.program.extend(self.gate_map.get_qubic_gateinstr(gatename, qubits))

    def visit_QuantumReset(self, node: QASMNode):
        qubit_reg = node.qubits.name
        if self.qubits[qubit_reg] is None:
            hardware_qubits = [self.qubit_map.get_hardware_qubit(qubit_reg, None)]
        else:
            hardware_qubits = [self.qubit_map.get_hardware_qubit(qubit_reg, i) for i in range(self.qubits[qubit_reg])]

        for qubit in hardware_qubits:
            self.program.extend([
                {'name': 'read', 'qubit': qubit},
                {'name': 'branch_fproc', 'cond_lhs': 1, 'alu_cond': 'eq', 'func_id': f'{qubit}.meas', 'scope': qubit, 
                    'true': [
                        {'name': 'X90', 'qubit': qubit},
                        {'name': 'X90', 'qubit': qubit}],
                    'false': []}])


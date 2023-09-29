"""
Preliminary specification:
    qubits and gates:
        - quantum gates supported according to gate_map.GateMap
        - mapping between declared qubits (e.g. qubit q[n]) given by qubit_map.QubitMap
    classical variables:
        - all sized integers are cast to 32 bit native int types
        - all bit types are cast to an array of integers
        - all floats are cast to native amp types
        - all angles are cast to native phase types
    classical flow:
        - if/else are converted to branch_var statements
        - for and while loops are supported
            - break, continue not supported


"""

supported_op_dict = {
        '==': 'eq',
        '>': 'ge',
        '<': 'le',
        '+': 'add',
        '-': 'sub'}

NATIVE_INT_SIZE = 32

from openqasm3.visitor import QASMVisitor, QASMNode
import openqasm3.ast as ast
from distproc.openqasm.qubit_map import QubitMap, DefaultQubitMap
from distproc.openqasm.gate_map import GateMap, DefaultGateMap
import ipdb
import warnings
from attrs import define

@define
class _VariableContainer:
    var_names: list
    type: str = 'int'

class QASMQubiCVisitor(QASMVisitor):

    def __init__(self, qubit_map: QubitMap = DefaultQubitMap(), gate_map: GateMap = DefaultGateMap()):
        self.qubit_map = qubit_map
        self.gate_map = gate_map
        self.program = []
        self._cur_block = self.program #pointer to current instr list

        self.qubits = {}
        self.vars = {}
        self._tempvar_ind = 0
        super().__init__()

    def visit_QubitDeclaration(self, node: QASMNode, context=None):
        print(f"hello i am a qubit: {node.qubit.name}")
        if node.size is not None:
            self.qubits[node.qubit.name] = node.size.value
        else:
            self.qubits[node.qubit.name] = None


    def visit_QuantumGate(self, node: QASMNode, context=None):
        gatename = node.name.name
        print(f"hello i am a {gatename} in {context}")
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
        
        self._cur_block.extend(self.gate_map.get_qubic_gateinstr(gatename, qubits))

    def visit_QuantumReset(self, node: QASMNode, context=None):
        qubit_reg = node.qubits.name
        if self.qubits[qubit_reg] is None:
            hardware_qubits = [self.qubit_map.get_hardware_qubit(qubit_reg, None)]
        else:
            hardware_qubits = [self.qubit_map.get_hardware_qubit(qubit_reg, i) for i in range(self.qubits[qubit_reg])]

        for qubit in hardware_qubits:
            self._cur_block.extend([
                {'name': 'read', 'qubit': qubit},
                {'name': 'branch_fproc', 'cond_lhs': 1, 'alu_cond': 'eq', 'func_id': f'{qubit}.meas', 'scope': qubit, 
                    'true': [
                        {'name': 'X90', 'qubit': qubit},
                        {'name': 'X90', 'qubit': qubit}],
                    'false': []}])

    def visit_ClassicalDeclaration(self, node: QASMNode, context=None):
        if isinstance(node.type, ast.BitType):
            if node.type.size.value is None:
                self._cur_block.append({'name': 'declare', 'var': node.identifier.name})
                self.vars[node.identifier.name] = [node.identifier.name]
            else:
                self.vars[node.identifier.name] = []
                for i in range(node.type.size.value):
                    warnings.warn(f'casting bit into array of {node.type.size} integers')
                    indexed_varname = f'{node.identifier.name}_{i}'
                    self.vars[node.identifier.name].append(indexed_varname)
                    self._cur_block.append({'name': 'declare', 'var': indexed_varname})

        elif isinstance(node.type, ast.IntType):
            if node.type.size is not None and node.type.size != NATIVE_INT_SIZE:
                warnings.warn(f'casting integer of size {node.type.size} to {NATIVE_INT_SIZE}')
            self.vars[node.identifier.name] = [node.identifier.name]
            self._cur_block.append({'name': 'declare', 'var': indexed_varname})

    def visit_BranchingStatement(self, node: QASMNode, context=None):
        print(f'hello i am a branch in {context}')

        expr = self.visit(node.condition) #parse out the conditional expression


        #self._cur_block.append({'name': 'branch_var', 'cond_lhs': })

    def visit_BinaryExpression(self, node: QASMNode, context=None):
        """
        context has two modes:
            None: default; return a tuple (lhs, op, rhs) in terms of strings/primitive var names
            'primitive': return a single token containing the result of the expression, and 
                        add program statements declaring, setting this token accordingly
        """
        lhs_primitive = self.visit(node.lhs, 'primitive')
        rhs_primitive = self.visit(node.rhs, 'primitive')
        op = node.op.name

        if context == 'primitive':
            if lhs_primitive[:10] == '_temp_var_':
                self._cur_block.append({'name': 'alu', 'op': supported_op_dict[op], 'lhs': lhs_primitive, 
                                        'rhs': rhs_primitive, 'out': lhs_primitive})
                return lhs_primitive
            elif rhs_primitive[:10] == '_temp_var_':
                self._cur_block.append({'name': 'alu', 'op': supported_op_dict[op], 'lhs': lhs_primitive, 
                                        'rhs': rhs_primitive, 'out': rhs_primitive})
                return rhs_primitive
            else:
                temp_out = f'_temp_var_{self._tempvar_ind}'
                self._cur_block.append({'name': 'declare', 'var': temp_out})
                self._tempvar_ind += 1
                self._cur_block.append({'name': 'alu', 'op': supported_op_dict[op], 'lhs': lhs_primitive, 
                                        'rhs': rhs_primitive, 'out': temp_out})
                return temp_out



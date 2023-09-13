from abc import ABC, abstractmethod
import numpy as np

class GateMap(ABC):
    """
    Maps QASM gates to QChip gates. Excludes (arbitrary) virtual_z 
    gates (Z90, etc still included)
    """

    @abstractmethod
    def get_qubic_gateinstr(self, gatename: str, hardware_qubits: list) -> list:
        pass

class DefaultGateMap(GateMap):
    """
    TODO: maybe add decompositions for common gates, like hadamard
    """
    def __init__(self):
        self.native_gates = ['X90', 'CNOT', 'Y-90', 'Z90', 'CZ'] 
        self.qasm_supported_gates = ['x', 'y', 'z', 'h', 'cx', 'cz', 's']

    def _decompose_h(self, hardware_qubits: list) -> list:
        assert len(hardware_qubits) == 1
        return [{'name': 'virtual_z', 'phase': np.pi, 'qubit': hardware_qubits}, 
                {'name': 'Y-90', 'qubit': hardware_qubits}]

    def _decompose_x(self, hardware_qubits:list) -> list:
        assert len(hardware_qubits) == 1
        return [{'name': 'X90', 'qubit': hardware_qubits}, 
                {'name': 'X90', 'qubit': hardware_qubits}]
    
    def _decompose_z(self, hardware_qubits:list) -> list:
        return [{'name': 'virtual_z', 'phase': np.pi, 'qubit': hardware_qubits}]

    def get_qubic_gateinstr(self, gatename: str, hardware_qubits: list) -> list:
        #assert gatename in self.qasm_supported_gates
        if gatename == 'h':
            return self._decompose_h(hardware_qubits)
        elif gatename == 'x':
            return self._decompose_x(hardware_qubits)
        elif gatename == 'z':
            return self._decompose_z(hardware_qubits)
        elif gatename == 'cx':
            return [{'name': 'CNOT', 'qubit': hardware_qubits}]
        else:
            return [{'name': gatename.upper(), 'qubit': hardware_qubits}] #Exception(f'{gatename} not supported!')


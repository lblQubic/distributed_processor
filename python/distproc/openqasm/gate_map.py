from abc import ABC, abstractmethod

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

    def _decompose_h(self):
        pass

    def get_qubic_gateinstr(self, gatename: str, hardware_qubits: list) -> list:
        assert gatename in self.qasm_supported_gates
        return [{'name': gatename.upper(), 'qubit': hardware_qubits}]


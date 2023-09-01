from abc import ABC, abstractmethod

class QubitMap(ABC):

    @abstractmethod
    def get_hardware_qubit(self, qubit_reg: str, index: int):
        pass

class DefaultQubitMap(QubitMap):
    """
    Default qubit map, should work for most programs. Rule:
        q[ind] --> Qind
    """

    def __init__(self):
        super().__init__()

    def get_hardware_qubit(self, qubit_reg: str, index: int = None):
        if index is not None:
            return qubit_reg.upper() + str(index)
        else:
            return qubit_reg.upper()

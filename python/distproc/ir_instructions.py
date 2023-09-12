from attrs import define, field
import numpy as np

@define
class Gate:
    name: str
    _qubit: list | str
    modi: dict = None
    start_time: int = None
    scope: list | set | tuple = None

    @property
    def qubit(self):
        if isinstance(self._qubit, list):
            return self._qubit
        elif isinstance(self._qubit, tuple):
            return list(self._qubit)
        elif isinstance(self._qubit, str):
            return [self._qubit]
        else:
            raise TypeError

@define
class Pulse:
    freq: str | float
    phase: str | float
    amp: str | float
    twidth: float
    env: np.ndarray | dict
    dest: str
    start_time: int = None
    name: str = 'pulse'

@define
class VirtualZ:
    phase: float
    name: str = 'virtual_z'
    _qubit: str = None
    _freq: str | float = 'freq'
    scope: list | tuple | set = None

    @property
    def freq(self):
        if isinstance(self._freq, str):
            if self.qubit is not None:
                return ''.join(self.qubit) + f'.{self._freq}'
            else:
                return self._freq

        else:
            return self._freq

    @property
    def qubit(self):
        if self._qubit is None:
            return None
        elif isinstance(self._qubit, list):
            return self._qubit
        elif isinstance(self._qubit, str):
            return [self._qubit]
        else:
            raise TypeError


@define
class DeclareFreq:
    freq: float
    scope: list
    name: str = 'declare_freq'
    freqname: str = None
    freq_ind: int = None

@define
class BindPhase:
    var: str
    _qubit: str = None
    _freq: str | float = 'freq'
    name: str = 'bind_phase'
    scope: list | tuple | set = None

    @property
    def freq(self):
        if isinstance(self._freq, str):
            if self.qubit is not None:
                return ''.join(self.qubit) + f'.{self._freq}'
            else:
                return self._freq

        else:
            return self._freq

    @property
    def qubit(self):
        if self._qubit is None:
            return None
        elif isinstance(self._qubit, list):
            return self._qubit
        elif isinstance(self._qubit, str):
            return [self._qubit]
        else:
            raise TypeError

@define
class Barrier:
    name: str = 'barrier'
    qubit: list = None
    scope: list | tuple | set = None

@define
class Delay:
    t: float
    name: str = 'delay'
    qubit: list = None
    scope: list | tuple | set = None

@define
class JumpFproc:
    alu_cond: str
    cond_lhs: int | str
    func_id: int | str
    scope: list
    jump_label: str
    jump_type: str = None
    name: str = 'jump_fproc'

@define
class ReadFproc:
    func_id: int | str
    var: str
    scope: list | set = None
    name: str = 'read_fproc'

@define
class AluFproc:
    func_id: int | str
    lhs: int | str
    op: str
    out: str
    scope: list | set = None
    name: str = 'alu_fproc'

@define
class JumpLabel:
    label: str
    scope: set | list | tuple
    name: str = 'jump_label'

@define 
class JumpCond:
    cond_lhs: int | str
    alu_cond: str
    cond_rhs: str
    scope: list | set
    jump_label: str
    jump_type: str = None
    name: str = 'jump_cond'

@define
class JumpI:
    scope: list | set
    jump_label: str
    jump_type: str = None
    name: str = 'jump_i'

@define
class Declare:
    scope: list | set
    var: str
    dtype: str = 'int' # 'int', 'phase', or 'amp'
    name: str = 'declare'

@define
class LoopEnd:
    scope: list | set | tuple
    loop_label: str
    name: str = 'loop_end'

@define
class Alu:
    op: str
    lhs: str | int | float
    rhs: str
    out: str
    scope: list | set = None
    name: str = 'alu'

@define
class SetVar:
    value: int | float
    var: str
    scope: list | set = None
    name: str = 'set_var'

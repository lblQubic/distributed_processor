"""
"""
from abc import ABC, abstractmethod
from attrs import define, field
import distproc.command_gen as cg
import numpy as np
import json

class ElementConfig(ABC):
    """
    TODO: standardize constructor args for GlobalAssembler usage
    """

    def __init__(self, fpga_clk_period, samples_per_clk):
        self.fpga_clk_period = fpga_clk_period
        self.samples_per_clk = samples_per_clk

        #TODO: move these out of this class:
        self.nclks_alu = 2
        self.nclks_br_fproc = 2
        self.nclks_read_fproc = 2
        self.elems_per_core = 3

    @property
    def sample_period(self):
        return self.fpga_clk_period/self.samples_per_clk

    @property
    def sample_freq(self):
        return 1/self.sample_period

    @property
    def fpga_clk_freq(self):
        return 1/self.fpga_clk_period

    @abstractmethod
    def get_phase_word(self, phase):
        pass

    @abstractmethod
    def length_nclks(self, tlength):
        pass

    @abstractmethod
    def get_env_word(self, env_start_ind, env_length):
        pass

    @abstractmethod
    def get_cw_env_word(self, env_start_ind):
        pass

    @abstractmethod
    def get_env_buffer(self, env):
        pass

    @abstractmethod
    def get_freq_buffer(self, freqs):
        pass

    @abstractmethod
    def get_freq_addr(self, freq_ind):
        pass

    @abstractmethod
    def get_cfg_word(self, elem_ind, mode_bits):
        pass

    @abstractmethod
    def get_amp_word(self, amplitude):
        pass


@define
class FPGAConfig:
    fpga_clk_period: float
    alu_instr_clks: int
    jump_cond_clks: int
    jump_fproc_clks: int
    pulse_regwrite_clks: int
    pulse_load_clks: int = 4

    @property
    def fpga_clk_freq(self):
        return 1/self.fpga_clk_period

@define
class ChannelConfig:
    core_ind : int
    elem_ind : int
    elem_params : dict
    _env_mem_name : str
    _freq_mem_name : str
    _acc_mem_name : str

    @property
    def env_mem_name(self):
        return self._env_mem_name.format(core_ind=self.core_ind)

    @property
    def freq_mem_name(self):
        return self._freq_mem_name.format(core_ind=self.core_ind)
    
    @property
    def acc_mem_name(self):
        return self._acc_mem_name.format(core_ind=self.core_ind)


def load_channel_configs(config_dict):

    if isinstance(config_dict, str):
        with open(config_dict) as f:
            config_dict = json.load(f)

    assert 'fpga_clk_freq' in config_dict.keys()

    channel_configs = {}

    for key, value in config_dict.items():
        if isinstance(value, dict):
            channel_configs[key] = ChannelConfig(**value)

        else:
            channel_configs[key] = value 

    return channel_configs

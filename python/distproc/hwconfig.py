"""
"""
from abc import ABC, abstractmethod
from attrs import define, field
import distproc.command_gen as cg
import numpy as np
import json

FPROC_MEAS_CLKS = 64
N_CORES = 8

class ElementConfig(ABC):
    """
    TODO: standardize constructor args for GlobalAssembler usage
    """

    def __init__(self, fpga_clk_period, samples_per_clk):
        self.fpga_clk_period = fpga_clk_period
        self.samples_per_clk = samples_per_clk

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
class FPROCChannel:
    """
    Description of an FPROC channel. Meant to be part of 
    FPGAConfig.fproc_channels, which is a dict with (key, value)
    pairs consisting of (name of the channel, FPROCChannel object)

    Attributes
    ----------
        id: int or tuple

            if int, the ID used to query the FPROC

            if tuple, the actual resolution of the ID is done in 
            the assemble stage using the channel_config object. The
            first element of the tuple is the key of the object, and
            the second element is the attribute to access

        hold_after_chans:
            list of pulse destination channels to server as reference 
            points for delay and idle. i.e. delay/idle are applied relative
            to the (end of) the last pulse played on any of these channels.

        hold_nclks: float
            delay (in seconds) to apply to pulses played after a 
            read_fproc or branch_fproc instruction on this channel
    """
    id: int | tuple
    hold_after_chans: list = field(factory=list)
    hold_nclks: int = 0

@define
class FPGAConfig:
    fpga_clk_period: float = 2.e-9
    alu_instr_clks: int = 5
    jump_cond_clks: int = 5
    jump_fproc_clks: int = 5
    pulse_regwrite_clks: int = 3
    pulse_load_clks: int = 3
    fproc_channels: dict = field(init=False)

    # sensible defaults for fproc_meas channels: each qubit gets a 'Qn.meas' channel,
    #  which is indexed according to the proc core for that qubit.
    def __attrs_post_init__(self):
        self.fproc_channels = {f'Q{i}.meas': FPROCChannel(id=(f'Q{i}.rdlo', 'core_ind'), 
                                                 hold_after_chans=[f'Q{i}.rdlo'], 
                                                 hold_nclks=FPROC_MEAS_CLKS) for i in range(N_CORES)}

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

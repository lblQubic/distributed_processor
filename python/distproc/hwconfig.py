"""
"""
from abc import ABC, abstractmethod
import distproc.command_gen as cg
import numpy as np

class ElementConfig(ABC):

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
    def get_freq_addr(self, freq):
        pass

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

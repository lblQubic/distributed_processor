"""
"""
from abc import ABC, abstractmethod
import distproc.command_gen as cg
import numpy as np

class HardwareConfig(ABC):

    def __init__(self, fpga_clk_period, dac_samples_per_clk, adc_samples_per_clk):
        self.fpga_clk_period = fpga_clk_period
        self.dac_samples_per_clk = dac_samples_per_clk
        self.adc_samples_per_clk = adc_samples_per_clk
        self.nclks_alu = 2
        self.nclks_br_fproc = 2
        self.nclks_read_fproc = 2

    @property
    def dac_sample_period(self):
        return self.fpga_clk_period/self.dac_samples_per_clk

    @property
    def adc_sample_period(self):
        return self.fpga_clk_period/self.adc_samples_per_clk

    @property
    def dac_sample_freq(self):
        return 1/self.dac_sample_period

    @property
    def adc_sample_freq(self):
        return 1/self.adc_sample_period

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
    def get_env_buffer(self, env_samples):
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

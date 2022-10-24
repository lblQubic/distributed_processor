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
        self.env_n_bits = 16

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
    def get_freq_word(self, freq):
        pass

    @abstractmethod
    def get_phase_word(self, phase):
        pass

    @abstractmethod
    def get_length_word(self, length):
        pass

    # TODO: maybe change these to abstract?
    def get_env_addr(self, env_ind):
        return env_ind//self.dac_samples_per_clk

    def get_env_buffer(self, env_samples):
        env_samples = np.pad(env_samples, (0, (self.dac_samples_per_clk - len(env_samples) \
                % self.dac_samples_per_clk) % self.dac_samples_per_clk))
        return cg.twos_complement(np.real(env_samples*2**(self.env_n_bits-1)).astype(int), nbits=self.env_n_bits) \
                    + (cg.twos_complement(np.imag(env_samples*2**(self.env_n_bits-1)).astype(int), nbits=self.env_n_bits) << self.env_n_bits)

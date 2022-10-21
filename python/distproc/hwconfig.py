"""
"""
from abc import ABC, abstractmethod

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
    def get_freq_word(self, freq):
        pass

    @abstractmethod
    def get_phase_word(self, phase):
        pass

    @abstractmethod
    def get_env_addr(self, env_ind):
        pass
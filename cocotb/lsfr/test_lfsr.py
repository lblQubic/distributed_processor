import cocotb
import random
import ipdb
import numpy as np
from cocotb.triggers import Timer, RisingEdge, ReadWrite
import distproc.command_gen as cg
import matplotlib.pyplot as plt

N_CLKS = 5000000
WIDTH = 16
CLK_CYCLE = 2

async def generate_clock(dut):
    for i in range(N_CLKS):
        dut.clk.value = 0
        await Timer(CLK_CYCLE, units='ns')
        dut.clk.value = 1
        await Timer(CLK_CYCLE, units='ns')
    dut._log.debug("clk cycle {}".format(i))

@cocotb.test()
async def test_ival_write(dut):
    cocotb.start_soon(generate_clock(dut))
    n_iters = int(1e6)
    dut.reset.value = 1
    await RisingEdge(dut.clk)
    dut.reset.value = 0

    rng_list = np.zeros(n_iters)

    for i in range(n_iters):
        await RisingEdge(dut.clk)
        rng_list[i] = int(dut.rand_out.value)

    ipdb.set_trace()
    rng_hist, bins = np.histogram(rng_list, np.arange(2**WIDTH))
    plt.plot(rng_hist)
    plt.show()




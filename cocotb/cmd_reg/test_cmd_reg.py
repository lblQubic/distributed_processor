import cocotb
import random
import ipdb
import numpy as np
from cocotb.triggers import Timer, RisingEdge, ReadWrite

PHASE_WIDTH=14
FREQ_WIDTH=24
N_CLKS = 100
CLK_CYCLE = 4

async def generate_clock(dut):
    for i in range(N_CLKS):
        dut.clk.value = 0
        await Timer(CLK_CYCLE, units='ns')
        dut.clk.value = 1
        await Timer(CLK_CYCLE, units='ns')
    dut._log.debug("clk cycle {}".format(i))

@cocotb.test()
async def test_cmd_reg(dut):
    cocotb.start_soon(generate_clock(dut))
    phase = np.pi/2
    freq = 200.e6
    env_start_addr = 10

    tref_start = 0

    await(RisingEdge(dut.clk))
    dut.phase_offs_in.value = int(phase*2**PHASE_WIDTH/(2*np.pi))
    dut.freq_in.value = int(freq*2**FREQ_WIDTH/1.e9)
    dut.env_addr_in.value = env_start_addr
    dut.phase_write_en.value = 1
    dut.freq_write_en.value = 1
    dut.env_addr_write_en.value = 1
    dut.tref.value = 0

    await(RisingEdge(dut.clk))
    await(ReadWrite())
    phase_out = int(dut.phase.value)
    freq_out = int(dut.freq.value)
    env_addr_out = int(dut.env_addr.value)

    assert phase_out == int(phase*2**PHASE_WIDTH/(2*np.pi))
    assert freq_out == int(freq*2**FREQ_WIDTH/1.e9)
    assert env_addr_out == env_start_addr

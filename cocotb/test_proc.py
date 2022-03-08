import cocotb
import random
from cocotb.triggers import Timer, RisingEdge

CLK_CYCLE = 5
N_CLKS = 150

async def generate_clock(dut):
    for i in range(N_CLKS):
        dut.clk.value = 0
        await Timer(CLK_CYCLE, units='ns')
        dut.clk.value = 1
        await Timer(CLK_CYCLE, units='ns')
    dut._log.debug("clk cycle {}".format(i))

async def load_commands(dut, cmd_list, start_addr=0):
    addr = start_addr
    for cmd in cmd_list:
        dut.cmd_data.value = cmd
        dut.cmd_addr.value = addr
        dut.write_prog_enable.value = 1
        await RisingEdge(dut.clk)
        addr += 1

    dut.write_prog_enable.value = 0

@cocotb.test()
async def cmd_mem_out_test(dut):
    """
    write some stuff to the command memory, trigger,
    and make sure they come out sequentially. Note:
    set opcodes to 0 to keep in proper state
    """
    n_cmd = 20
    cmd_list = []

    for i in range(n_cmd):
        cmd_list.append(random.randint(0,2**120-1))

    await cocotb.start(generate_clock(dut))

    await load_commands(dut, cmd_list)
    dut.reset.value = 1
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.reset.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)

    cmd_read_list = []
    qclk_val = []
    for i in range(n_cmd):
        cmd_read_list.append(dut.cmd_buf_out.value)
        qclk_val.append(dut.qclk_out.value)
        #print('i ' + str(i))
        #print('qclk_val ' + str(dut.qclk_out))
        #print('qclk_rst ' + str(dut.myclk.rst))
        await RisingEdge(dut.clk)

    for i in range(n_cmd):
        #print('cmd_out {}'.format(int(cmd_list[i])))
        #print('cmd_in {}'.format(int(cmd_read_list[i])))
        #print(qclk_val[i])
        #print ('..........................')
        assert cmd_read_list[i] == cmd_list[i]

    #dut._log.info("clk val {}".format(dut.clk))

@cocotb.test()
async def pulse_cmd_out_test(dut):
    n_cmd = 20
    cmd_list = []

    for i in range(n_cmd):
        cmd_list.append(random.randint(0,2**120-1))

    await cocotb.start(generate_clock(dut))

    await load_commands(dut, cmd_list)
    dut.reset.value = 1
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.reset.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)

    cmd_read_list = []
    qclk_val = []
    for i in range(n_cmd):
        cmd_read_list.append(dut.cmd_out.value)
        qclk_val.append(dut.qclk_out.value)
        await RisingEdge(dut.clk)

    for i in range(n_cmd):
        cmd = cmd_list[i] >> 16
        cmd = cmd%(2**72)
        #print('........................................')
        #print('cmd_out {:0b}'.format(int(cmd_list[i])))
        #print('cmd_cut_out {:0b}'.format(int(cmd)))
        #print('cmd_in {:0b}'.format(int(cmd_read_list[i])))
        assert cmd_read_list[i] == cmd

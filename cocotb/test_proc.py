import cocotb
import random
import numpy as np
from cocotb.triggers import Timer, RisingEdge
import command_gen as cg

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
    set opcodes to 00001 to keep in proper state, and
    make sure execution doesn't stop
    """
    n_cmd = 20
    cmd_list = []

    for i in range(n_cmd):
        cmd_list.append(random.randint(0,2**120-1) + (1<<123))

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
    """
    same as cmd_mem_out_test, but check the cmd_out
    port instead of the output of the command memory
    directly
    """
    n_cmd = 20
    cmd_list = []

    for i in range(n_cmd):
        cmd_list.append(random.randint(0,2**120-1) + (1<<123))

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

@cocotb.test()
async def pulse_cmd_trig_test(dut):
    n_cmd = 11
    cmd_list = []
    cmd_body_list = []
    cmd_time_list = [2, 3, 4, 7, 8, 9, 15, 16, 18, 19, 22]

    for i in range(n_cmd):
        cmd_body = random.randint(0, 2**72)
        cmd_body_list.append(cmd_body)
        cmd_list.append((cmd_body << 16) + (cmd_time_list[i] << (16 + 72)))
    
    await cocotb.start(generate_clock(dut))
    await load_commands(dut, cmd_list)
    dut.reset.value = 1
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.reset.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)

    cmd_read_list = []
    cmd_read_times = []
    for i in range(25):
        if(dut.cstrobe.value == 1):
            cmd_read_list.append(dut.cmd_out.value)
            cmd_read_times.append(dut.qclk_out.value)
        await RisingEdge(dut.clk)

    dut._log.debug('command in: {}'.format(cmd_body_list))
    dut._log.debug('command time in: {}'.format(cmd_time_list))
    dut._log.debug('command out: {}'.format(cmd_read_list))
    dut._log.debug('command time out: {}'.format(cmd_read_times))
    for i in range(n_cmd):
        assert cmd_body_list[i] == cmd_read_list[i]
        assert cmd_time_list[i] == cmd_read_times[i]
    #assert np.all(np.asarray(cmd_body_list) == np.asarray(cmd_read_list).astype(int))
    #assert np.all(np.asarray(cmd_time_list) == np.asarray(cmd_read_times).astype(int))

@cocotb.test()
async def regwrite_i_test(dut):
    reg_addr = random.randint(0,15)
    reg_val = random.randint(0, 2**32-1)

    cmd = (0b00001000 << 120) + (reg_val << 88) + (reg_addr << 80)

    await cocotb.start(generate_clock(dut))
    await load_commands(dut, [cmd])

    dut.reset.value = 1
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.reset.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    #await RisingEdge(dut.clk)

    reg_read = dut.regs.data[reg_addr].value

    assert(reg_read == reg_val)

@cocotb.test()
async def reg_i_test(dut):
    """
    Write a value to a random register. Then, perform an operation
    on that register and an intermediate value, and store in another register.
    """
    cmd_list = []
    reg_addr0 = random.randint(0,15)
    reg_addr1 = random.randint(0,15)
    #reg_val = random.randint(0, 2**32-1)
    #ival = random.randint(0, 2**32-1)
    reg_val = random.randint(-2**31, 2**31-1)
    ival = random.randint(-2**31, 2**31-1)
    op = random.choice(['add', 'sub', 'le', 'ge', 'eq'])
    
    cmd_list.append(cg.reg_i_alu(reg_val, 'id', 0, reg_addr0))
    cmd_list.append(cg.reg_i_alu(ival, op, reg_addr0, reg_addr1))

    dut._log.debug('cmd 0 in: {}'.format(bin(cmd_list[0])))
    dut._log.debug('cmd 1 in: {}'.format(bin(cmd_list[1])))

    await cocotb.start(generate_clock(dut))
    await load_commands(dut, cmd_list)

    dut.reset.value = 1
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.reset.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)

    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    reg_read_val = dut.regs.data[reg_addr1].value
    if op == 'add':
        correct_val = reg_val + ival
    elif op == 'sub':
        correct_val = ival - reg_val
    elif op == 'ge':
        correct_val = int(ival > reg_val)
    elif op == 'le':
        correct_val = int(ival < reg_val)
    elif op == 'eq':
        correct_val = int(reg_val == ival)

    dut._log.debug('reg val in: {}'.format(reg_val))
    dut._log.debug('i val in: {}'.format(ival))
    dut._log.debug('op: {}'.format(op))
    dut._log.debug('val out: {}'.format(reg_read_val.signed_integer))
    dut._log.debug('correct val out: {}'.format(correct_val))

    assert reg_read_val.signed_integer == correct_val

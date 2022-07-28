import numpy as np
import ipdb
#from instr_params.vh
#TODO: consider refactoring this into fewer functions,
#      since many ALU instructions have the same structure
#      UPDATE: consider depracating more specific cg functions
alu_opcodes = {'id0' : 0b000,
               'id1' : 0b110,
               'add' : 0b001,
               'sub' : 0b010,
               'eq' : 0b011,
               'le' : 0b100,
               'ge' : 0b101,
               'zero' : 0b111}

opcodes = {'reg_alu_i' : 0b00010, #|opcode[8]|cmd_value[32]|reg_addr[4]|reg_write_addr[4]
           'reg_alu' : 0b00011, #|opcode[8]|reg_addr[4]|resrv[28]|reg_addr[4]|reg_write_addr[4]
           'jump_i' : 0b00100, #|opcode[8]|cmd_value[32]|reg_addr[4]
           'jump_cond_i' : 0b00110, #|opcode[8]|cmd_value[32]|reg_addr[4]|instr_ptr_addr[8]
           'jump_cond' : 0b00111, #jump address is always immediate
           'alu_fproc' : 0b01001,
           'alu_fproc_i' : 0b01000,
           'jump_fproc_i' : 0b01010,
           'jump_fproc' : 0b01011,
           'inc_qclk_i' : 0b01100,
           'inc_qclk' : 0b01101,
           'sync' : 0b01110}


def pulse_i(freq, phase, env_start_addr, env_length, cmd_time):
    """
    Returns 128-bit command corresponding to timed pulse output.
    This is configured for processor in QubiC dsp_unit gateware.

    Parameters
    ----------
        freq : float
            pulse carrier freq in Hz
            range: [0, 1.e9)
        phase : float
            initial carrier phase in rad 
            range: [0, 2pi)
        env_start_addr : int
            start address of pulse envelope
        env_length : int
            number of envelope samples
        cmd_time : int
            pulse start time, in FPGA clock units

    """
    freq_int = int((freq/1.e9) * 2**24)
    phase_int = int((phase/(2*np.pi) * 2**14))
    #cmd_word = (env_start_addr << 50) + (env_length << 38) + (phase_int << 24) + freq_int
    if env_length % 4 != 0:
        raise Exception('length of envelope must be a multiple of 4!')
    cmd_word = (env_start_addr << 50) + ((env_length//4) << 38) + (phase_int << 24) + freq_int
    return (cmd_word << 24) + (cmd_time << 88)

def reg_alu_i(value, alu_op, reg_addr, reg_write_addr):
    """
    Returns 128-bit command corresponding to:
        *reg_write_addr = value <alu_op> *reg_addr
    
    Parameters
    ----------
        value : int (max 32 bit, signed or unsigned)
        alu_op : str
            one of: 'id', 'add', 'sub', 'eq', 'le', 'ge'
        reg_addr : int (unsigned, max 4 bit)
        reg_write_addr : int (unsigned, max 4 bit)

    Returns
    -------
        cmd : int
            128 bit command
    """
    opcode = (opcodes['reg_alu_i'] << 3) + alu_opcodes[alu_op]
    #print('reg_fn_opcode:', bin(opcode))
    return (opcode << 120) + (twos_complement(value) << 88) + (reg_addr << 84) + (reg_write_addr << 80)

def reg_alu(reg_addr0, alu_op, reg_addr1, reg_write_addr):
    """
    Returns 128-bit command corresponding to:
        *reg_write_addr = *reg_addr0 <alu_op> *reg_addr1
    
    Parameters
    ----------
        reg_addr0 : int (unsigned, max 4 bit)
        alu_op : str
            one of: 'id', 'add', 'sub', 'eq', 'le', 'ge'
        reg_addr1 : int (unsigned, max 4 bit)
        reg_write_addr : int (unsigned, max 4 bit)

    Returns
    -------
        cmd : int
            128 bit command
    """
    opcode = (opcodes['reg_alu_i'] << 3) + alu_opcodes[alu_op]
    return (opcode << 120) + (reg_addr0 << 116) + (reg_addr1 << 84) + (reg_write_addr << 80)

def jump_i(instr_ptr_addr):
    opcode = opcodes['jump_i'] << 3
    return (opcode << 120) + (instr_ptr_addr << 76)

def jump_cond_i(value, alu_op, reg_addr, instr_ptr_addr):
    """
    Returns 128-bit command corresponding to a conditional
        jump to instr_ptr_addr if:
            value <alu_op> *reg_addr1 evaluates to true
    
    Parameters
    ----------
        value : int (max 32 bit, signed or unsigned)
        alu_op : str
            one of: 'eq', 'le', 'ge'
        reg_addr : int (unsigned, max 4 bit)
        reg_write_addr : int (unsigned, max 4 bit)
        instr_ptr_addr : int (unsigned max 8 bit)

    Returns
    -------
        cmd : int
            128 bit command
    """
    assert alu_op == 'eq' or alu_op == 'le' or alu_op == 'ge'
    opcode = (opcodes['jump_cond_i'] << 3) + alu_opcodes[alu_op]
    return (opcode << 120) + (twos_complement(value) << 88) + (reg_addr << 84) + (instr_ptr_addr << 76)

def jump_cond(reg_addr0, alu_op, reg_addr1, instr_ptr_addr):
    """
    Returns 128-bit command corresponding to a conditional
        jump to instr_ptr_addr if:
            value <alu_op> *reg_addr1 evaluates to true
    
    Parameters
    ----------
        reg_addr : int (unsigned, max 4 bit)
        alu_op : str
            one of: 'eq', 'le', 'ge'
        reg_addr : int (unsigned, max 4 bit)
        reg_write_addr : int (unsigned, max 4 bit)
        instr_ptr_addr : int (unsigned max 8 bit)

    Returns
    -------
        cmd : int
            128 bit command
    """
    assert alu_op == 'eq' or alu_op == 'le' or alu_op == 'ge'
    opcode = (opcodes['jump_cond_i'] << 3) + alu_opcodes[alu_op]
    return (opcode << 120) + (reg_addr0 << 116) + (reg_addr1 << 84) + (instr_ptr_addr << 76)

def inc_qclk_i(inc_val):
    opcode = (opcodes['inc_qclk_i'] << 3) + alu_opcodes['add']
    return (opcode << 120) + (twos_complement(inc_val) << 88)

def inc_qclk(inc_reg_addr):
    opcode = (opcodes['inc_qclk'] << 3) + alu_opcodes['add']
    return (opcode << 120) + (inc_reg_addr << 116)

def alu_fproc(func_id, alu_reg_addr, alu_op, write_reg_addr):
    opcode = (opcodes['alu_fproc'] << 3) + alu_opcodes[alu_op]
    return (opcode << 120) + (alu_reg_addr << 116) + (write_reg_addr << 80) + (func_id << 68)

def read_fproc(func_id, write_reg_addr):
    """
    This is an alias of alu_fproc
    """
    return alu_fproc(func_id, 0, 'id1', write_reg_addr)

def jump_fproc(func_id, alu_reg_addr, alu_op, instr_ptr_addr):
    opcode = (opcodes['jump_fproc'] << 3) + alu_opcodes[alu_op]
    return (opcode << 120) + (alu_reg_addr << 116) + (instr_ptr_addr << 76) + (func_id << 68)

def jump_fproc_i(func_id, value, alu_op, instr_ptr_addr):
    opcode = (opcodes['jump_fproc_i'] << 3) + alu_opcodes[alu_op]
    return (opcode << 120) + (value << 88) + (instr_ptr_addr << 76) + (func_id << 68)

def alu_cmd(optype, im_or_reg, alu_in0, alu_op, alu_in1=None, write_reg_addr=None, jump_cmd_ptr=None, func_id=None):
    """
    This is a general function for generating the following types of instructions:
        reg_(i)alu, jump_cond(i), alu_fproc(i), jump_fproc(i)

    Parameters
    ----------
        optype : str
            one of: reg_alu, jump_cond, alu_fproc, jump_fproc
        im_or_reg : str
            'i' for immediate instruction and 'r' for register based
        alu_in0 : int
            if immediate, value; if register, reg addr
        alu_op : str
            alu opcode
        alu_in1 : int
            alu reg addr
        write_reg_addr : int
            reg address to write alu output
        jump_cmd_ptr : int
        func_id : int
    """
    cmd = 0
    if optype in ['reg_alu', 'jump_cond']: #these have alu_in1 from reg
        cmd += alu_in1 << 84
    if optype in ['alu_fproc', 'jump_fproc']:
        if func_id is not None:
            cmd += func_id << 68
    if optype in ['jump_cond', 'jump_fproc']:
        cmd += jump_cmd_ptr << 76
    if optype in ['reg_alu', 'alu_fproc']:
        cmd += write_reg_addr << 80

    if im_or_reg == 'i':
        opkey = optype + '_i'
        cmd += twos_complement(alu_in0) << 88
    else:
        cmd += alu_in0 << 116

    opcode = (opcodes[opkey] << 3) + alu_opcodes[alu_op]
    cmd += opcode << 120

    return cmd


def twos_complement(value, nbits=32):
    """
    Returns the nbits twos complement value of a standard signed python 
    integer or list of ints

    Parameters
    ----------
        value : int or list of ints
        nbits : int (positive)

    Returns
    -------
        int or list of ints
    """
    if isinstance(value, int):
        value_array = np.array([value])
    else:
        value_array = np.array(value)

    if np.any((value_array > (2**(nbits-1) - 1)) | (value_array < (-2**(nbits-1)))):
        raise Exception('{} out of range'.format(value))

    posmask = value_array >= 0
    negmask = value_array < 0

    value_array[negmask] = 2**nbits + value_array[negmask]

    if isinstance(value, int):
        return int(value_array[0])
    else:
        return value_array



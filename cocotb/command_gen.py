#from instr_params.vh
alu_opcodes = {'id' : 0b000,
               'add' : 0b001,
               'sub' : 0b010,
               'eq' : 0b011,
               'le' : 0b100,
               'ge' : 0b101,
               'zero' : 0b111}

opcodes = {'reg_i_alu' : 0b00001, #|opcode[8]|cmd_value[32]|reg_addr[4]|reg_write_addr[4]
           'reg_alu' : 0b00010, #|opcode[8]|reg_addr[4]|resrv[28]|reg_addr[4]|reg_write_addr[4]
           'jump_i' : 0b00011, #|opcode[8]|cmd_value[32]|reg_addr[4]
           'jump_cond_i' : 0b00100, #|opcode[8]|cmd_value[32]|reg_addr[4]|instr_ptr_addr[8]
           'jump_cond' : 0b00101, #jump address is always immediate
           'read_fproc' : 0b00110,
           'jump_i_fproc' : 0b00111,
           'jump_fproc' : 0b00111,
           'inc_qclk_i' : 0b01000,
           'inc_qclk' : 0b01001,
           'sync' : 0b01010,
           'reg_write_i' : 0b01011}


def pulse_command():
    return 0

def reg_i_alu(value, alu_op, reg_addr, reg_write_addr):
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
    opcode = (opcodes['reg_i_alu'] << 3) + alu_opcodes[alu_op]
    #print('reg_fn_opcode:', bin(opcode))
    return (opcode << 120) + (twos_complement(value) << 88) + (reg_addr << 84) + (reg_write_addr << 80)

def reg_alu(reg_addr0, alu_op, reg_addr, reg_write_addr):
    """
    Returns 128-bit command corresponding to:
        *reg_write_addr = *reg_addr0 <alu_op> *reg_addr1
    
    Parameters
    ----------
        reg_addr : int (unsigned, max 4 bit)
        alu_op : str
            one of: 'id', 'add', 'sub', 'eq', 'le', 'ge'
        reg_addr : int (unsigned, max 4 bit)
        reg_write_addr : int (unsigned, max 4 bit)

    Returns
    -------
        cmd : int
            128 bit command
    """
    opcode = (opcodes['reg_i_alu'] << 3) + alu_opcodes[alu_op]
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
    assert alu_opcode == 'eq' or alu_opcode == 'le' or alu_opcode == 'ge'
    opcode = (opcodes['jump_cond_i'] << 3) + alu_opcodes[alu_op]
    return (opcode << 120) + (reg_addr0 << 116) + (reg_addr1 << 84) + (instr_ptr_addr << 76)

def twos_complement(value, nbits=32):
    """
    Returns the nbits twos complement value of a standard signed python integer

    Parameters
    ----------
        value : int
        nbits : int (positive)

    Returns
    -------
        int
    """
    if value > (2**(nbits-1) - 1) or value < (-2**(nbits-1)):
        raise Exception('{} out of range'.format(value))
    elif value >= 0:
        return value
    else:
        return 2**nbits + value

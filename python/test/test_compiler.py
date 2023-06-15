import pytest
import numpy as np
import ipdb
import distproc.compiler as cm
import distproc.assembler as am
import distproc.hwconfig as hw
import qubitconfig.qchip as qc
import json

class ElementConfigTest(hw.ElementConfig):
    def __init__(self, samples_per_clk, interp_ratio):
        super().__init__(2.e-9, samples_per_clk)

    def get_phase_word(self, phase):
        return 0

    def get_env_word(self, env_start_ind, env_length):
        return 0

    def get_env_buffer(self, env_samples):
        return np.zeros(10)

    def get_freq_buffer(self, freqs):
        return np.zeros(10)

    def get_freq_addr(self, freq_ind):
        return 0

    def get_amp_word(self, amplitude):
        return 0

    def length_nclks(self, tlength):
        return int(np.ceil(tlength/self.fpga_clk_period))

    def get_cfg_word(self, elem_ind, mode_bits):
        return elem_ind

def test_phase_resolve():
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    fpga_config = hw.FPGAConfig(**fpga_config)
    qchip = qc.QChip('qubitcfg.json')
    program = []
    program.append({'name':'X90', 'qubit': ['Q0']})
    program.append({'name':'X90', 'qubit': ['Q1']})
    program.append({'name':'X90Z90', 'qubit': ['Q0']})
    program.append({'name':'X90', 'qubit': ['Q0']})
    program.append({'name':'virtualz', 'qubit': ['Q0'], 'phase': np.pi/4})
    program.append({'name':'X90', 'qubit': ['Q0']})
    program.append({'name':'X90', 'qubit': ['Q1']})
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)
    compiler.compile()
    resolved_prog = compiler._basic_blocks['block_0'].resolved_program
    assert resolved_prog[0].contents[0].phase == 0
    assert resolved_prog[1].contents[0].phase == 0
    assert resolved_prog[3].contents[0].phase == np.pi/2
    assert resolved_prog[4].contents[0].phase == 3*np.pi/4
    assert resolved_prog[5].contents[0].phase == 0

def test_basic_schedule():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name':'X90', 'qubit': ['Q0']},
            {'name':'X90', 'qubit': ['Q1']},
            {'name':'X90Z90', 'qubit': ['Q0']},
            {'name':'X90', 'qubit': ['Q0']},
            {'name':'X90', 'qubit': ['Q1']},
            {'name':'read', 'qubit': ['Q0']}]
    fpga_config = hw.FPGAConfig(**fpga_config)
    channel_configs = hw.load_channel_configs('../test/channel_config.json')
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)
    compiler.schedule()
    scheduled_prog = compiler._basic_blocks['block_0'].scheduled_program
    assert scheduled_prog[0]['t'] == 5
    assert scheduled_prog[1]['t'] == 5
    assert scheduled_prog[2]['t'] == 21 #scheduled_prog[0]['gate'].contents[0].twidth
    assert scheduled_prog[3]['t'] == 37 #scheduled_prog[0]['gate'].contents[0].twidth \
            #+ scheduled_prog[2]['gate'].contents[0].twidth
    assert scheduled_prog[4]['t'] == 13 #scheduled_prog[1]['gate'].contents[0].twidth
    assert scheduled_prog[5]['t'] == 53 #scheduled_prog[0]['gate'].contents[0].twidth \
              #+ scheduled_prog[2]['gate'].contents[0].twidth + scheduled_prog[3]['gate'].contents[0].twidth
def test_pulse_compile():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name':'X90', 'qubit': ['Q0']},
               {'name':'X90', 'qubit': ['Q1']},
               {'name':'X90Z90', 'qubit': ['Q0']},
               {'name':'X90', 'qubit': ['Q0']},
               {'name':'X90', 'qubit': ['Q1']},
               {'name': 'pulse', 'phase': 'np.pi/2', 'freq': 'Q0.freq', 'env': np.ones(100), 
                'twidth': 24.e-9, 'amp':0.5, 'dest': 'Q0.qdrv'},
               {'name':'read', 'qubit': ['Q0']}]
    fpga_config = hw.FPGAConfig(**fpga_config)
    channel_configs = hw.load_channel_configs('../test/channel_config.json')
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)
    prog = compiler.compile()
    sorted_program = {key: prog.program[key] for key in sorted(prog.program.keys())}
    with open('test_outputs/test_pulse_compile_out.txt', 'r') as f:
        assert str(sorted_program) == f.read().rstrip('\n')
    return prog

def test_pulse_compile_nogate():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name': 'pulse', 'phase': 'np.pi/2', 'freq': 'Q0.freq', 'env': np.ones(100), 
                'twidth': 24.e-9, 'amp':0.5, 'dest': 'Q0.qdrv'},
               {'name': 'pulse', 'phase': 'np.pi/2', 'freq': 'Q0.freq', 'env': np.ones(100, dtype=np.float32), 
                'twidth': 24.e-9, 'amp':0.5, 'dest': 'Q0.rdrv'},
               {'name': 'pulse', 'phase': 'np.pi/2', 'freq': 'Q0.freq', 'env': np.ones(100), 
                'twidth': 24.e-9, 'amp':0.5, 'dest': 'Q0.qdrv'},
               {'name': 'pulse', 'phase': 'np.pi/2', 'freq': 1234234, 'env': np.ones(100), 
                'twidth': 24.e-9, 'amp':0.5, 'dest': 'Q1.qdrv'},
               {'name':'read', 'qubit': ['Q0']}]
    fpga_config = hw.FPGAConfig(**fpga_config)
    channel_configs = hw.load_channel_configs('../test/channel_config.json')
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)
    prog = compiler.compile()
    print(prog.program)
    return prog

def test_basic_compile():
    #can we compile without errors
    pass
    # wiremap = wm.Wiremap('wiremap_test0.json')
    # qchip = qc.QChip('qubitcfg.json')
    # compiler = cm.Compiler(['Q0', 'Q1'], wiremap, qchip, ElementConfigTest())
    # compiler.add_statement({'name':'X90', 'qubit':'Q0'})
    # compiler.add_statement({'name':'X90', 'qubit':'Q1'})
    # compiler.add_statement({'name':'X90Z90', 'qubit':'Q0'})
    # compiler.add_statement({'name':'X90', 'qubit':'Q0'})
    # compiler.add_statement({'name':'X90', 'qubit':'Q1'})
    # compiler.add_statement({'name':'read', 'qubit':'Q0'})
    # compiler.compile()
    # compiler.generate_sim_output()
    # assert True


def test_linear_cfg():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name': 'X90', 'qubit': ['Q0']},
               {'name': 'X90', 'qubit': ['Q1']}]
    fpga_config = hw.FPGAConfig(**fpga_config)
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)
    compiler._make_basic_blocks()
    print('basic_blocks{}'.format(compiler._basic_blocks))
    compiler._generate_cfg()
    print('cfg {}'.format(compiler._control_flow_graph))
    assert True


def test_onebranch_cfg():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name': 'X90', 'qubit': ['Q0']},
               {'name': 'branch_fproc', 'alu_cond': 'eq', 'cond_lhs': 0, 
                'func_id': 0, 'true': [{'name': 'X90', 'qubit': ['Q0']}],
                'false': [{'name': 'X90', 'qubit': ['Q1']}], 'scope':['Q0', 'Q1']},
               {'name': 'X90', 'qubit': ['Q1']}]
    fpga_config = hw.FPGAConfig(**fpga_config)
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)
    compiler._make_basic_blocks()
    compiler._generate_cfg()
    for blockname, block in compiler._basic_blocks.items():
        print('{}: {}'.format(blockname, block))

    for source, dest in compiler._control_flow_graph.items():
        print('{}: {}'.format(source, dest))
    for source, dest in compiler._global_cfg.items():
        print('{}: {}'.format(source, dest))
    assert True


def test_multrst_cfg():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name': 'X90', 'qubit': ['Q0']},
               {'name': 'branch_fproc', 'alu_cond': 'eq', 'cond_lhs': 1, 'func_id': 1,
                'true': [],
                'false': [{'name': 'X90', 'qubit': ['Q0']}], 'scope':['Q0']},
               {'name': 'branch_fproc', 'alu_cond': 'eq', 'cond_lhs': 1, 'func_id': 0,
                'true': [],
                'false': [{'name': 'X90', 'qubit': ['Q1']}], 'scope':['Q1']},
               {'name': 'X90', 'qubit': ['Q1']}]
    fpga_config = hw.FPGAConfig(**fpga_config)
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)
    compiler._make_basic_blocks()
    compiler._generate_cfg()
    print('basic_blocks:')
    for blockname, block in compiler._basic_blocks.items():
        print('{}: {}'.format(blockname, block))

    for source, dest in compiler._control_flow_graph.items():
        print('{}: {}'.format(source, dest))
    for source, dest in compiler._global_cfg.items():
        print('{}: {}'.format(source, dest))

    prog = compiler.compile()
    sorted_program = {key: prog.program[key] for key in sorted(prog.program.keys())}
    with open('test_outputs/test_multirst_cfg.txt', 'r') as f:
        #f.write(str(prog.program))
        assert str(sorted_program) == f.read().rstrip('\n')

    assert True

def test_linear_compile():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name': 'X90', 'qubit': ['Q0']},
               {'name': 'X90', 'qubit': ['Q1']},
               {'name': 'read', 'qubit': ['Q0']}]
    fpga_config = hw.FPGAConfig(**fpga_config)
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)
    for blockname, block in compiler._basic_blocks.items():
        print('{}: {}'.format(blockname, block))

    for source, dest in compiler._control_flow_graph.items():
        print('{}: {}'.format(source, dest))
    for source, dest in compiler._global_cfg.items():
        print('{}: {}'.format(source, dest))
    compiler.schedule()
    prog = compiler.compile()
    print()
    print('lincomp_prog')
    print(prog.program)
    sorted_program = {key: prog.program[key] for key in sorted(prog.program.keys())}
    with open('test_outputs/test_linear_compile_out.txt', 'r') as f:
        #f.write(str(prog.program))
        assert str(sorted_program) == f.read().rstrip('\n')

def test_linear_compile_globalasm():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name': 'X90', 'qubit': ['Q0']},
               {'name': 'X90', 'qubit': ['Q1']},
               {'name': 'read', 'qubit': ['Q0']}]
    fpga_config = hw.FPGAConfig(**fpga_config)
    channel_configs = hw.load_channel_configs('../test/channel_config.json')
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)
    compiled_prog = compiler.compile()
    #compiled_prog = cm.CompiledProgram(compiler.asm_progs, fpga_config)

    globalasm = am.GlobalAssembler(compiled_prog, channel_configs, ElementConfigTest)
    asm_prog = globalasm.get_assembled_program()
    sorted_prog = {chan_ind: {buffer: asm_prog[chan_ind][buffer] for buffer in sorted(asm_prog[chan_ind].keys())} 
                      for chan_ind in sorted(asm_prog.keys())}
    with open('test_outputs/test_linear_compile_globalasm.txt', 'r') as f:
        assert str(sorted_prog) == f.read().rstrip('\n')

def test_multrst_schedule():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name': 'X90', 'qubit': ['Q0']},
               {'name': 'branch_fproc', 'alu_cond': 'eq', 'cond_lhs': 1, 'func_id': 0,
                'true': [],
                'false': [{'name': 'X90', 'qubit': ['Q0']}], 'scope':['Q0']},
               {'name': 'read', 'qubit': ['Q1']},
               {'name': 'branch_fproc', 'alu_cond': 'eq', 'cond_lhs': 1, 'func_id': 1,
                'true': [],
                'false': [{'name': 'X90', 'qubit': ['Q1']}], 'scope':['Q1']},
               {'name': 'X90', 'qubit': ['Q1']}]
    fpga_config = hw.FPGAConfig(**fpga_config)
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)

    compiler._make_basic_blocks()
    print('basic_blocks:')
    for blockname, block in compiler._basic_blocks.items():
        print('{}: {}'.format(blockname, block))

    compiler._generate_cfg()
    for source, dest in compiler._control_flow_graph.items():
        print('{}: {}'.format(source, dest))
    for source, dest in compiler._global_cfg.items():
        print('{}: {}'.format(source, dest))

    compiler.schedule()
    for source, dest in compiler.block_end_times.items():
        print('{}: {}'.format(source, dest))

    assert True
    return compiler.compile()

def test_multrst_schedule2():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name': 'X90', 'qubit': ['Q0']},
               {'name': 'read', 'qubit': ['Q0']},
               {'name': 'X90', 'qubit': ['Q1']},
               {'name': 'read', 'qubit': ['Q1']},
               {'name': 'branch_fproc', 'alu_cond': 'eq', 'cond_lhs': 1, 'func_id': 1,
                'true': [],
                'false': [{'name': 'X90', 'qubit': ['Q0']}], 'scope':['Q0']},
               {'name': 'branch_fproc', 'alu_cond': 'eq', 'cond_lhs': 1, 'func_id': 0,
                'true': [],
                'false': [{'name': 'X90', 'qubit': ['Q1']}], 'scope':['Q1']},
               {'name': 'X90', 'qubit': ['Q1']}]
    fpga_config = hw.FPGAConfig(**fpga_config)
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)

    compiler._make_basic_blocks()
    print('basic_blocks:')
    for blockname, block in compiler._basic_blocks.items():
        print('{}: {}'.format(blockname, block))

    compiler._generate_cfg()
    for source, dest in compiler._control_flow_graph.items():
        print('{}: {}'.format(source, dest))
    for source, dest in compiler._global_cfg.items():
        print('{}: {}'.format(source, dest))

    compiler.schedule()
    for source, dest in compiler.block_end_times.items():
        print('{}: {}'.format(source, dest))

    assert True
    return compiler.compile()

def test_simple_loop():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name': 'X90', 'qubit': ['Q0']},
               {'name': 'read', 'qubit': ['Q0']},
               {'name': 'X90', 'qubit': ['Q1']},
               {'name': 'Z90', 'qubit': ['Q0']},
               {'name': 'X90', 'qubit': ['Q0']},
               {'name': 'declare', 'var': 'loopind', 'dtype': 'int', 'scope': ['Q0']},
               {'name': 'loop', 'cond_lhs': 10, 'cond_rhs': 'loopind', 'alu_cond': 'ge', 
                'scope': ['Q0'], 'body':[
                    {'name': 'X90', 'qubit': ['Q0']},
                    {'name': 'X90', 'qubit': ['Q0']}]},
               {'name': 'read', 'qubit': ['Q0']},
               {'name': 'X90', 'qubit': ['Q1']}]

    fpga_config = hw.FPGAConfig(**fpga_config)
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)

    compiler._make_basic_blocks()
    print('basic_blocks:')
    for blockname, block in compiler._basic_blocks.items():
        print('{}: {}'.format(blockname, block))

    compiler._generate_cfg()
    for source, dest in compiler._control_flow_graph.items():
        print('{}: {}'.format(source, dest))
    for source, dest in compiler._global_cfg.items():
        print('{}: {}'.format(source, dest))

    compiler.schedule()
    for source, dest in compiler.block_end_times.items():
        print('{}: {}'.format(source, dest))

    assert True
    prog = compiler.compile()
    sorted_program = {key: prog.program[key] for key in sorted(prog.program.keys())}
    with open('test_outputs/test_simple_loop.txt', 'r') as f:
        #f.write(str(sorted_program))
        assert str(sorted_program) == f.read().rstrip('\n')

def test_compound_loop():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name': 'X90', 'qubit': ['Q0']},
               {'name': 'read', 'qubit': ['Q0']},
               {'name': 'X90', 'qubit': ['Q1']},
               {'name': 'declare', 'var': 'loopind', 'dtype': 'int', 'scope': ['Q0']},
               {'name': 'loop', 'cond_lhs': 10, 'cond_rhs': 'loopind', 'alu_cond': 'ge', 
                'scope': ['Q0', 'Q1'], 'body':[
                    {'name': 'X90', 'qubit': ['Q0']},
                    {'name': 'X90', 'qubit': ['Q0']}]},
               {'name': 'CR', 'qubit': ['Q1', 'Q0']},
               {'name': 'X90', 'qubit': ['Q1']}]

    fpga_config = hw.FPGAConfig(**fpga_config)
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)

    compiler._make_basic_blocks()
    print('basic_blocks:')
    for blockname, block in compiler._basic_blocks.items():
        print('{}: {}'.format(blockname, block))

    compiler._generate_cfg()
    for source, dest in compiler._control_flow_graph.items():
        print('{}: {}'.format(source, dest))
    for source, dest in compiler._global_cfg.items():
        print('{}: {}'.format(source, dest))

    compiler.schedule()
    for source, dest in compiler.block_end_times.items():
        print('{}: {}'.format(source, dest))

    prog = compiler.compile()
    sorted_program = {key: prog.program[key] for key in sorted(prog.program.keys())}
    with open('test_outputs/test_compound_loop.txt', 'r') as f:
        #f.write(str(prog.program))
        assert str(sorted_program) == f.read().rstrip('\n')
    return prog

def test_nested_loop():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    program = [{'name': 'X90', 'qubit': ['Q0']},
               {'name': 'read', 'qubit': ['Q0']},
               {'name': 'X90', 'qubit': ['Q1']},
               {'name': 'declare', 'var': 'loopind', 'dtype': 'int', 'scope': ['Q0']},
               {'name': 'declare', 'var': 'loopind2', 'dtype': 'int', 'scope': ['Q0']},
               {'name': 'loop', 'cond_lhs': 10, 'cond_rhs': 'loopind', 'alu_cond': 'ge', 
                'scope': ['Q0', 'Q1'], 'body':[
                    {'name': 'X90', 'qubit': ['Q0']},
                    {'name': 'X90', 'qubit': ['Q0']},
                    {'name': 'loop', 'cond_lhs': 10, 'cond_rhs': 'loopind2', 'alu_cond': 'ge',
                     'scope': ['Q0', 'Q1'], 'body':[
                         {'name': 'X90', 'qubit': ['Q1']},
                         {'name': 'read', 'qubit': ['Q0']}]}]},
               {'name': 'CR', 'qubit': ['Q1', 'Q0']},
               {'name': 'X90', 'qubit': ['Q1']}]

    fpga_config = hw.FPGAConfig(**fpga_config)
    compiler = cm.Compiler(program, 'by_qubit', fpga_config, qchip)

    compiler._make_basic_blocks()
    print('basic_blocks:')
    for blockname, block in compiler._basic_blocks.items():
        print('{}: {}'.format(blockname, block))

    compiler._generate_cfg()
    for source, dest in compiler._control_flow_graph.items():
        print('{}: {}'.format(source, dest))
    for source, dest in compiler._global_cfg.items():
        print('{}: {}'.format(source, dest))

    compiler.schedule()
    for source, dest in compiler.block_end_times.items():
        print('{}: {}'.format(source, dest))

    prog = compiler.compile()
    sorted_program = {key: prog.program[key] for key in sorted(prog.program.keys())}
    with open('test_outputs/test_nested_loop.txt', 'r') as f:
        assert str(sorted_program) == f.read().rstrip('\n')
    return prog

def test_scoper_procgroup_gen():
    scoper = cm._Scoper(('Q0.rdrv', 'Q0.rdlo', 'Q0.qdrv', 'Q1.rdrv', 'Q1.qdrv', 'Q1.rdlo'))
    grouping = {dest: ('Q0.qdrv', 'Q0.rdrv', 'Q0.rdlo') for dest in ('Q0.rdrv', 'Q0.rdlo', 'Q0.qdrv')}
    grouping.update({dest: ('Q1.qdrv', 'Q1.rdrv', 'Q1.rdlo') for dest in ('Q1.rdrv', 'Q1.rdlo', 'Q1.qdrv')})
    assert json.dumps(scoper.proc_groupings, sort_keys=True) == json.dumps(grouping, sort_keys=True)

def test_scoper_procgroup_gen_bychan():
    scoper = cm._Scoper(('Q0.rdrv', 'Q0.rdlo', 'Q0.qdrv', 'Q1.rdrv', 'Q1.qdrv', 'Q1.rdlo'), 
                        proc_grouping=[('{qubit}.qdrv',), ('{qubit}.rdrv', '{qubit}.rdlo')])
    grouping = {dest: ('Q0.rdrv', 'Q0.rdlo') for dest in ('Q0.rdrv', 'Q0.rdlo')}
    grouping.update({'Q0.qdrv': ('Q0.qdrv',)})
    grouping.update({dest: ('Q1.rdrv', 'Q1.rdlo') for dest in ('Q1.rdrv', 'Q1.rdlo')})
    grouping.update({'Q1.qdrv': ('Q1.qdrv',)})
    #print(scoper.proc_groupings)
    assert json.dumps(scoper.proc_groupings, sort_keys=True) == json.dumps(grouping, sort_keys=True)

import pytest
import numpy as np
import ipdb
import distproc.compiler as cm
import distproc.hwconfig as hw
import qubitconfig.qchip as qc
import qubitconfig.wiremap as wm

class ElementConfigTest(hw.ElementConfig):
    def __init__(self):
        super().__init__(2.e-9, 16)

    def get_phase_word(self, phase):
        return 0

    def get_env_word(self, env_start_ind, env_length):
        return 0

    def get_env_buffer(self, env_samples):
        return 0

    def get_freq_buffer(self, freqs):
        return 0

    def get_freq_addr(self, freq_ind):
        return 0

    def get_amp_word(self, amplitude):
        return 0

    def length_nclks(self, tlength):
        return int(np.ceil(tlength/self.fpga_clk_period))

    def get_cfg_word(self, elem_ind, mode_bits):
        return elem_ind

def test_phase_resolve():
    pass
    # wiremap = wm.Wiremap('wiremap_test0.json')
    # qchip = qc.QChip('qubitcfg.json')
    # compiler = cm.Compiler(['Q0', 'Q1'], wiremap, qchip, ElementConfigTest())
    # compiler.add_statement({'name':'X90', 'qubit':'Q0'})
    # compiler.add_statement({'name':'X90', 'qubit':'Q1'})
    # compiler.add_statement({'name':'X90Z90', 'qubit':'Q0'})
    # compiler.add_statement({'name':'X90', 'qubit':'Q0'})
    # compiler.add_statement({'name':'X90', 'qubit':'Q1'})
    # resolved_prog = compiler._resolve_gates(compiler._program)
    # resolved_prog = compiler._resolve_virtualz_pulses(resolved_prog)
    # assert resolved_prog[0].contents[0].pcarrier == 0
    # assert resolved_prog[1].contents[0].pcarrier == 0
    # assert resolved_prog[3].contents[0].pcarrier == np.pi/2
    # assert resolved_prog[4].contents[0].pcarrier == 0

def test_basic_schedule():
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
    # resolved_prog = compiler._resolve_gates(compiler._program)
    # resolved_prog = compiler._resolve_virtualz_pulses(resolved_prog)
    # scheduled_prog = compiler.schedule(resolved_prog)
    # assert scheduled_prog[0]['t'] == 0
    # assert scheduled_prog[1]['t'] == 0
    # assert scheduled_prog[2]['t'] == 8 #scheduled_prog[0]['gate'].contents[0].twidth
    # assert scheduled_prog[3]['t'] == 16 #scheduled_prog[0]['gate'].contents[0].twidth \
    #         #+ scheduled_prog[2]['gate'].contents[0].twidth
    # assert scheduled_prog[4]['t'] == 4 #scheduled_prog[1]['gate'].contents[0].twidth
    # assert scheduled_prog[5]['t'] == 24 #scheduled_prog[0]['gate'].contents[0].twidth \
                #+ scheduled_prog[2]['gate'].contents[0].twidth + scheduled_prog[3]['gate'].contents[0].twidth

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
    compiler = cm.Compiler('by_qubit', fpga_config, qchip)
    program = [{'name': 'X90', 'qubit': 'Q0'},
               {'name': 'X90', 'qubit': 'Q1'}]
    compiler.from_list(program)
    compiler.make_basic_blocks()
    compiler.generate_cfg()
    print('basic_blocks{}'.format(compiler._basic_blocks))
    print('cfg {}'.format(compiler._control_flow_graph))
    assert True

def test_onebranch_cfg():
    qchip = qc.QChip('qubitcfg.json')
    fpga_config = {'alu_instr_clks': 2,
                   'fpga_clk_period': 2.e-9,
                   'jump_cond_clks': 3,
                   'jump_fproc_clks': 4,
                   'pulse_regwrite_clks': 1}
    compiler = cm.Compiler('by_qubit', fpga_config, qchip, ['Q0', 'Q1'])
    program = [{'name': 'X90', 'qubit': ['Q0']},
               {'name': 'branch_fproc', 'alu_cond': 'eq', 'cond_rhs': 0, 
                'true': [{'name': 'X90', 'qubit': ['Q0']}],
                'false': [{'name': 'X90', 'qubit': ['Q1']}], 'scope':['Q0', 'Q1']},
               {'name': 'X90', 'qubit': ['Q1']}]
    compiler.from_list(program)
    compiler.make_basic_blocks()
    compiler.generate_cfg()
    ipdb.set_trace()
    print('basic_blocks{}'.format(compiler._basic_blocks))
    print('cfg {}'.format(compiler._control_flow_graph))
    assert True

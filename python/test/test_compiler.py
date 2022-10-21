import pytest
import numpy as np
import distproc.compiler as cm
import qubitconfig.qchip as qc
import qubitconfig.wiremap as wm

def test_phase_resolve():
    wiremap = wm.Wiremap('wiremap_test0.json')
    qchip = qc.QChip('qubitcfg.json')
    compiler = cm.Compiler(['Q0', 'Q1'], wiremap, qchip, None)
    compiler.add_statement({'name':'X90', 'qubit':'Q0'})
    compiler.add_statement({'name':'X90', 'qubit':'Q1'})
    compiler.add_statement({'name':'X90Z90', 'qubit':'Q0'})
    compiler.add_statement({'name':'X90', 'qubit':'Q0'})
    compiler.add_statement({'name':'X90', 'qubit':'Q1'})
    resolved_prog = compiler._resolve_gates(compiler._program)
    resolved_prog = compiler._resolve_virtualz_pulses(resolved_prog)
    assert resolved_prog[0].contents[0].pcarrier == 0
    assert resolved_prog[1].contents[0].pcarrier == 0
    assert resolved_prog[3].contents[0].pcarrier == np.pi/2
    assert resolved_prog[4].contents[0].pcarrier == 0

def test_basic_schedule():
    wiremap = wm.Wiremap('wiremap_test0.json')
    qchip = qc.QChip('qubitcfg.json')
    compiler = cm.Compiler(['Q0', 'Q1'], wiremap, qchip, None)
    compiler.add_statement({'name':'X90', 'qubit':'Q0'})
    compiler.add_statement({'name':'X90', 'qubit':'Q1'})
    compiler.add_statement({'name':'X90Z90', 'qubit':'Q0'})
    compiler.add_statement({'name':'X90', 'qubit':'Q0'})
    compiler.add_statement({'name':'X90', 'qubit':'Q1'})
    compiler.add_statement({'name':'read', 'qubit':'Q0'})
    resolved_prog = compiler._resolve_gates(compiler._program)
    resolved_prog = compiler._resolve_virtualz_pulses(resolved_prog)
    scheduled_prog = compiler.schedule(resolved_prog)
    assert scheduled_prog[0]['t'] == 0
    assert scheduled_prog[1]['t'] == 0
    assert scheduled_prog[2]['t'] == scheduled_prog[0]['gate'].contents[0].twidth
    assert scheduled_prog[3]['t'] == scheduled_prog[0]['gate'].contents[0].twidth \
            + scheduled_prog[2]['gate'].contents[0].twidth
    assert scheduled_prog[4]['t'] == scheduled_prog[1]['gate'].contents[0].twidth
    assert scheduled_prog[5]['t'] == scheduled_prog[0]['gate'].contents[0].twidth \
                + scheduled_prog[2]['gate'].contents[0].twidth + scheduled_prog[3]['gate'].contents[0].twidth

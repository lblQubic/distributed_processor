"""
Compiler layer for distributed processor. Program is input as a list of 
dicts encoding gates + branching operations. Each instruction dict has a 
'name' key followed by other instruction specific keys. 

TODO: add coredest to wiremap and parse this out in compiler

Instruction dict format:
    gate instructions: {'name': gatename, 'qubit': qubitid, 'modi': gate_param_mod_dict}
        gatename can be any named gate in the QChip object (qubitconfig.json), aside
        from names reserved for other operations described below. Named gate in QChip 
        object is gatename concatenated with qubitid (e.g. for the 'Q0read' gate you'd 
        use gatename='read' and qubitid='Q0'
    measure/store instruction: 
        {'name': 'measure', 'qubit': qubitid, 'modi': gate_param_mod_dict, 'dest': var_name}
        can store measurement result in named variable var_name, to be used for branching, etc,
        later on. Optional 'scope' key to specify qubits using the variable. Otherwise, scope
        is determined automatically by compiler.
    store fproc instruction:
        {'name': 'store_fproc', 'fproc_id': function_id, 'dest': var_name}
        stores fproc result (next available from fproc_id) in variable var_name for use 
        later in the program.
    barrier: {'name': 'barrier', 'qubits': qubitid_list}
        reference all subsequent gates to a common start time after the barrier (set by 
        the latest gate/measurement on any qubit in qubitid_list)
    sync: {'name': 'sync', 'barrier_id': id, 'qubits': qubitid_list}
        synchronizes the gate time references between the cores corresponding to the qubits
        in qubitid_list.
    branch instructions: 
        branch on variable/measurement/fproc_id. General format is:
        {value0: [instruction_list], value1: [instruction_list]...}

        branch_fproc: {'name': 'branch_fproc', 'fproc_id': function_id, value0: ...}
        branch directly on latest (next available) fprc result.

        branch_var: {'name': 'branch_var', 'var': var_name, ...}
        branch on previously stored variable
    ALU instructions:
        {'name': 'add' or 'sub' or 'le' or 'ge' or 'eq', 'in0': var_name, 'in1': var_name or value}


    Note about instructions using function processor (FPROC): these instructions are scheduled
    immediately and use the next available function proc output. Which measurements are actually
    used for this depend on the configuration of the function processor. For flexibility, we don't 
    impose a particular configuration in this layer. It is the responsibilty of the programmer 
    to understand the configuration and schedule these instructions using appropriate delays, 
    etc as necessary.

    The measure/store instruction assumes an fproc_id mapping between qubits and raw measurements;
    this is not guaranteed to work across all FPROC implementations (TODO: maybe add software checks
    for this...)
"""

import numpy as np
import matplotlib.pyplot as plt
import os
import sys

import qubitconfig.qchip as qc
import distproc.assembler as asm

RESRV_NAMES = ['branch_fproc', 'branch_var', 'barrier', 'delay', 'sync', 'virtualz']


class Compiler:
    def __init__(self, proc_groups, fpga_config_dict, qchip, qubits=None):

        self.qchip = qchip
        if qubits is None:
            self.qubits = qchip.qubits.keys()
        else:
            self.qubits = qubits

        if isinstance(proc_groups, list):
            self.asm_progs = {grp : [] for grp in proc_groups}
        elif proc_groups == 'by_qubit':
            self.asm_progs = {['{}.qdrv'.format(q), '{}.rdrv'.format(q), '{}.rdlo'.format(q)] : [] for q in self.qubits}
        elif proc_groups == 'by_channel':
            self.asm_progs = {['{}.qdrv'.format(q)]: [] for q in self.qubits} 
            self.asm_progs.update({['{}.rdrv'.format(q)]: [] for q in self.qubits})
            self.asm_progs.update({['{}.rdlo'.format(q)]: [] for q in self.qubits})
        else:
            raise ValueError('{} group not supported'.format(proc_groups))

        self.zphase = {} #keys: Q0.freq, Q1.freq, etc; values: zphase
        self.chan_to_core = {} # maps qubit channels (e.g. Q0.qdrv) to core in asm dict
        for qubit in self.qubits:
            for chantype in ['qdrv', 'rdrv', 'rdlo']:
                chan = '{}.{}'.format(qubit, chantype)
                for grp in self.asm_progs.keys():
                    if chan in grp:
                        self.chan_to_core[chan] = grp
                        break

            for freqname in qchip.qubit_dict[qubit].keys():
                self.zphase[qubit + '.' + freqname] = 0

    def add_statement(self, statement_dict, index=-1):
        if index == -1:
            self._program.append(statement_dict)
        else:
            self._program.insert(index, statement_dict)
        self._isscheduled = False
        self._isresolved = False

    def generate_cfg(self):
        self._basic_blocks = {'block0': []}
        self._control_flow_graph = {'block0': []}
        self._control_blocks = {}

        next_blockind = 0
        next_ctrlind = 0
        for instr in self._program:
            if instr['name'] in ['branch_fproc', 'branch_var']:
                self._control_blocks['ctrl{}'.format(next_ctrlind)] = \
                        {'name': instr['name']}
            elif instr['name'] == 'for_loop':
                pass

    def get_compiled_program(self):
        pass

    def from_list(self, prog_list):
        pass

    def compile(self):
        pass

    def generate_sim_output(self, n_samples=5000):
        destdict = {}
        for chan, ind in self.coredict.items():
            destdict[ind] = np.zeros((2, n_samples))
        for instr in self._scheduled_program:
            if 'gate' in instr.keys():
                for pulse in instr['gate'].get_pulses():
                    pulse_env = pulse.env.get_samples(dt=self.hwconfig.dac_sample_period, twidth=pulse.twidth, amp=pulse.amp)[1]
                    sample_inds = np.arange(0, len(pulse_env))
                    lofreq = self.wiremap.lofreq[pulse.dest]
                    phases = pulse.pcarrier + 2*np.pi*(pulse.fcarrier-lofreq)*self.hwconfig.dac_sample_period*(sample_inds + 4*(instr['t']+1))
                    scale_factor = 2**15 #TODO: fix hardcoding
                    pulse_i = scale_factor*(np.real(pulse_env)*np.cos(phases) - np.imag(pulse_env)*np.sin(phases))
                    pulse_q = scale_factor*(np.imag(pulse_env)*np.cos(phases) + np.real(pulse_env)*np.sin(phases))
                    start_time = instr['t']*self.hwconfig.dac_samples_per_clk
                    destdict[self.wiremap.coredict[pulse.dest]][0, start_time:start_time+len(pulse_env)] = pulse_i
                    destdict[self.wiremap.coredict[pulse.dest]][1, start_time:start_time+len(pulse_env)] = pulse_q
            else:
                raise Exception('{} not yet implemented'.format(instr['name']))
        return destdict


class BasicBlock:
    """
    Class for representing "basic blocks" in a qubic program. Basic blocks are program segments
    with linear control flow; i.e. they consist only of gate/barrier sequences. Each basic block
    is scoped to some subset of qubits used by the circuit. This class has methods for scheduling gates
    within the basic block and determining the total delta t.

    TODO:
        maybe add stuff for modifying program?
            - gate parameters
            - contents

    methods:
        schedule

    attributes:
        program : high-level qubic program
        scheduled_program: program with added execution time in 't' key
        delta_t: total execution time of basic block, in fpga clocks
    """

    def __init__(self, program, fpga_config, qchip, swphase=True):
        self._program = program
        self._fpga_config = fpga_config
        self._scope()
        for qubit in self.qubit_scope:
            for freqname in qchip.qubit_dict[qubit].keys():
                self.zphase[qubit + '.' + freqname] = 0
        self.is_resolved = False
        self.is_scheduled = False
        self.is_zresolved = not swphase
        self._swphase = swphase
        if not swphase:
            raise Exception('HW phases not yet implemented!')

    def _scope(self):
        self.qubit_scope = []
        for statement in self._program:
            if 'qubit' in statement.keys():
                self.qubit_scope.extend(statement['qubit'])
        self.qubit_scope = list(np.unique(np.asarray(self.qubit_scope)))

    def schedule(self):
        if not self.is_resolved:
            self._resolve_gates()
        if not self.is_zresolved:
            self._resolve_virtualz_pulses()
        qubit_last_t = {q: 0 for q in self.qubit_scope}
        self.scheduled_program = []
        for gate in self.resolved_program:
            if isinstance(gate, dict):
                if gate['name'] == 'barrier':
                    qubit_max_t = max([qubit_last_t[qubit] for qubit in gate['qubit']])
                    for qubit in gate['qubit']:
                        qubit_last_t[qubit] = qubit_max_t
                elif gate['name'] == 'delay':
                    if 'qubit' not in gate:
                        gate['qubit'] = self.qubit_scope
                    elif isinstance(gate['qubit'], str):
                        gate['qubit'] = [gate['qubit']]
                    for qubit in gate['qubit']:
                        qubit_last_t[qubit] += gate['t']
                else:
                    raise Exception('{} not yet implemented'.format(gate['name']))
                continue
            pulses = gate.get_pulses()
            min_pulse_t = []
            for pulse in pulses:
                qubit = pulse.dest[:2]
                assert qubit in self.qubit_scope
                qubit_t = qubit_last_t[qubit]
                min_pulse_t.append(qubit_t - self._get_pulse_nclks(pulse.t0))
            gate_t = max(min_pulse_t)
            for pulse in pulses:
                qubit_last_t[pulse.dest[:2]] = gate_t + self._get_pulse_nclks(pulse.t0) + self._get_pulse_nclks(pulse.twidth)
            self.scheduled_program.append({'gate': gate, 't': gate_t})
        self.delta_t = max(qubit_last_t.values())

    def _resolve_gates(self):
        """
        convert gatedict references to objects, then dereference (i.e.
        all gate.contents elements are GatePulse objects)
        """
        self.resolved_program = []
        for gatedict in self.resolved_program:
            if gatedict['name'] in RESRV_NAMES:
                self.resolved_program.append(gatedict)
                continue
            if isinstance(gatedict['qubit'], str):
                gatedict['qubit'] = [gatedict['qubit']]
            gatename = ''.join(gatedict['qubit']) + gatedict['name']
            gate = self.qchip.gates[gatename].copy()
            if 'modi' in gatedict and gatedict['modi'] is not None:
                gate = gate.get_updated_copy(gatedict['modi'])
            gate.dereference()
            self.resolved_program.append(gate)
        self.is_resolved = True

    def _get_pulse_nclks(self, length_secs):
        return int(np.ceil(length_secs/self._fpga_config['clk_period']))

    def _resolve_virtualz_pulses(self, resolved_program):
        zresolved_program = []
        for gate in resolved_program:
            if isinstance(gate, qc.Gate):
                gate = gate.copy()
                for pulse in gate.contents:
                    # TODO: fix config/encoding of these
                    if pulse.is_zphase:
                        self.zphase[pulse.fcarriername] += pulse.pcarrier
                    else:
                        pulse.pcarrier += self.zphase[pulse.fcarriername]
                gate.remove_virtualz()
                if len(gate.contents) > 0:
                    zresolved_program.append(gate)
            else:
                zresolved_program.append(gate)

        return zresolved_program

    def compile(self, tstart=0):
        if not self._isresolved and self.is_scheduled:
            raise Exception('schedule and resolve gates first!')
        for instr in self.scheduled_program:
            if 'gate' in instr.keys():
                for pulse in instr['gate'].get_pulses():
                    coreind = self.wiremap.coredict[pulse.dest]
                    elemind = self.wiremap.elemdict[pulse.dest]
                    # lofreq = self.wiremap.lofreq[pulse.dest]
                    self.assemblers[coreind].add_pulse(pulse.fcarrier - lofreq, pulse.pcarrier, instr['t'], \
                            pulse.env.get_samples(dt=self.hwconfig.dac_sample_period, twidth=pulse.twidth, amp=pulse.amp)[1], elemind)
            else:
                raise Exception('{} not yet implemented'.format(instr['name']))

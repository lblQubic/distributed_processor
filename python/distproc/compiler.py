"""
Compiler layer for distributed processor. Program is input as a list of 
dicts encoding gates and processor instructions. Each instruction dict has a 
'name' key followed by other instruction specific keys. 

Instruction dict format:
    gate instructions: 
        {'name': gatename, 'qubit': [qubitid], 'modi': gate_param_mod_dict, 'reg_param': (pulseind, attribute, name)}

        gatename can be any named gate in the QChip object (qubitconfig.json), aside
        from names reserved for other operations described below. Named gate in QChip 
        object is gatename concatenated with qubitid (e.g. for the 'Q0read' gate you'd 
        use gatename='read' and qubitid='Q0'). 'modi' and 'reg_param' are optional.

    pulse instructions:
        {'name': 'pulse', 'freq': <float or str> , 'phase': <float (radians)>, 'amp': <float>, 
         'twidth': <float>, 'env': <np.ndarray (samples) or dict>, 'dest': <str>}

        params is a dict of pulse parameters, formatted the same way as pulses in qubitcfg.json files 
        (or alternatively GatePulse object cfg_dicts)

    virtual-z gates:
        {'name': 'virtual_z', 'qubit': [qubitid], 'phase': phase_in_rad, 'freq': freq_name}

        'qubit', and 'freq' are both optional, but at least one must be specified. These fields are 
        used to resolve the name of the frequency that the phase increment gets applied to:
            - if both are specified, the freq name gets resolved to '<qubitid>.<freq_name>'
            - if only 'qubit' is specified, the freq name gets resolved to '<qubitid>.freq'. 
              (i.e. the default freq_name is 'freq')
            - if only 'freq' is specified, the freq name gets resolved to '<freq_name>'.

        'phase' is phase in radians

    frequency declaration:
        {'name': 'declare_freq', 'freq': freq_in_Hz, scope: <list_of_qubits_or_channels>, 'freq_ind': <hw_index>}

        Declares a frequency to be used by the specified qubits or channels. 'freq_ind' can subsequently be 
        referenced by a register (i.e. if 'reg_param' is set to parameterize a pulse frequency). If 'freq_ind' 
        is not set in the instruction, it is inferred implicitly by incrementing the previous freq_ind, starting from 
        0. Note that scheduling a gate/pulse with a previously unused frequency will implicitly cause it to
        be declared in the assembly program.

    z-phase parameterization:
        By default, all z-gates are implemented in software; all X90, etc pulse phases are set according to
        the preceding z-gates, and the z-gate instructions are removed from the program. However, this
        is not always possible when z-gates need to be applied conditionally. A z-phase can be bound
        to a processor register using the following instruction:

        {'name': 'bind_phase', 'freq': freq_name, 'var': reg_name}

        If this instruction is used, all z-gates applied to freq_name (frequency referenced in qchip;
        e.g. Q0.freq, Q1.readfreq, etc), are done in realtime on the processor, and all pulses using
        freq_name are phase parameterized by reg_name. reg_name must be declared separately.

        (this seems more like a compiler directive?)
        
    read fproc instruction:
        {'name': 'read_fproc', 'func_id': function_id, 'var': var_name, 'scope': qubits}

        stores fproc result (next available from func_id) in variable var_name for use 
        later in the program.

    alu fproc instruction:
        {'name': 'alu_fproc', 'func_id': function_id, 'lhs': immediate_or_varname, 'op': alu_op, 'out': destination_varname}

        performs an ALU operation on the fproc result (next available from func_id) and stores the result in
        destination_varname. That is, destination_varname = immmediate_or_varname [alu_op] fproc_result

    barrier: 
        {'name': 'barrier', 't': <delaytime in seconds> 'qubits': qubitid_list}

        add (software) delay between gates. 'qubits' is optional; if not specified assumed to be
        all qubits in the program

    delay: 
        {'name': 'delay', 'qubits': qubitid_list}

    sync: 
        {'name': 'sync', 'barrier_id': id, 'qubits': qubitid_list}

        synchronizes the gate time references between the cores corresponding to the qubits
        in qubitid_list.

    branch instructions: 
        {'name': 'branch_fproc', alu_cond: <'le' or 'ge' or 'eq'>, 'cond_lhs': <var or ival>, 
            'func_id': function_id, 'scope': <list_of_qubits> 'true': [instruction_list], 'false': [instruction_list]}
        branch directly on latest (next available) fproc result.

        {'name': 'branch_var', alu_cond: <'le' or 'ge' or 'eq'>, 'cond_lhs': <var or ival>, 
            'cond_rhs': var_name, 'scope': <list_of_qubits> 'true': [instruction_list], 'false': [instruction_list]}
        branch on variable

        {'name': 'loop', 'cond_lhs': <reg or ival>, 'cond_rhs': var_name, 'scope': <list_of_qubits>, 
            'body': [instruction_list]}
        repeats the instruction list 'body' when condition is true

    ALU instructions:
        {'name': 'alu', 'op': 'add' or 'sub' or 'le' or 'ge' or 'eq', 'lhs': var_name or value, 'rhs': var_name, 'out': output reg}

        {'name': 'set_var', 'value': immediate_value, 'var': varname}

    variable declaration:
        {'name': declare, 'var': varname, 'dtype': int or phase or amp, 'scope': qubits}


"""

import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
import os
import sys
import copy
import logging 
import parse
import re
from attrs import define

try:
    import ipdb
except ImportError:
    logging.warning('failed to import ipdb')
import json
from collections import OrderedDict

import qubitconfig.qchip as qc
import distproc.assembler as asm
import distproc.hwconfig as hw
import distproc.ir.ir as ir
import distproc.ir.passes as passes


@define
class CompilerFlags:
    resolve_gates: bool = True
    schedule: bool = True


def get_passes(fpga_config: hw.FPGAConfig, qchip: qc.QChip = None, 
               compiler_flags: CompilerFlags | dict = None,
               qubit_grouping=('{qubit}.qdrv', '{qubit}.rdrv', '{qubit}.rdlo'),
               proc_grouping=[('{qubit}.qdrv', '{qubit}.rdrv', '{qubit}.rdlo')]):

    if compiler_flags is None:
        compiler_flags = CompilerFlags()
    elif isinstance(compiler_flags, dict):
        compiler_flags = CompilerFlags(**compiler_flags)

    cur_passes = [passes.FlattenProgram(),
                  passes.MakeBasicBlocks()]

    cur_passes.extend([passes.ScopeProgram(qubit_grouping),
                       passes.RegisterVarsAndFreqs(qchip)])

    if compiler_flags.resolve_gates:
        if qchip is None:
            raise Exception('qchip object required for ResolveGates pass')
        cur_passes.append(passes.ResolveGates(qchip, qubit_grouping))

    cur_passes.extend([passes.GenerateCFG(),
                       passes.ResolveHWVirtualZ()])

    cur_passes.extend([passes.ResolveVirtualZ(),
                       passes.ResolveFreqs(),
                       passes.ResolveFPROCChannels(fpga_config),
                       passes.RescopeVars()])
    
    if compiler_flags.schedule:
        cur_passes.append(passes.Schedule(fpga_config, proc_grouping))

    else:
        cur_passes.append(passes.LintSchedule(fpga_config, proc_grouping))

    return cur_passes


class Compiler:
    """
    Class for compiling a quantum circuit encoded in the above format. Broadly, compilation has 
    three stages:
        1. Flatten the control flow heirarchy (see generate_flat_ir) and lower to intermediate
           representation. (see distproc.ir.IRProgram)
        2. Run a series of compiler passes on the IR. This is where the bulk of the compilation 
           happens, including:
               - gate resolution
               - virtualz phase resolution
               - scheduling
               - resolution of named frequencies
               - program block scoping
        3. Compile the program down to distributed processor assembly (CompiledProgram object).

    TODO:
        some linting checks:
            - bind_phase and declare statements before any pulses, etc 
            - sort out alu/read fproc instruction
            - change out to dest
    """

    def __init__(self, program, proc_grouping=[('{qubit}.qdrv', '{qubit}.rdrv', '{qubit}.rdlo')]):
        """
        Parameters
        ----------
            program : list of dicts
                program to compile, in QubiC circuit format
            proc_grouping : list of tuples
                list of tuples grouping channels to proc cores. Format keys
                (e.g. {qubit}) can be used to make general groupings.

        Preprocessing and lowering to IR (step 1 above) are performed in the constructor.
        """
        self.ir_prog = ir.IRProgram(program)
        self._proc_grouping = proc_grouping

    def run_ir_passes(self, passes: list):
        """
        Run a list of IR passes on the program. get_default_passes()
        can be used to generate this list in most cases.

        Parameters
        ----------
            passes : list
                list of passes. Each element is an ir.Pass object.
        """
        for ir_pass in passes:
            ir_pass.run_pass(self.ir_prog)

    def compile(self):
        """
        Compiler the program from the intermediate representation down to pulse-level 
        assembly (i.e. a CompiledProgram object). This includes splitting up the program
        statements into constituent distributed processor cores according to the 
        proc_grouping provided at Compiler instantiation

        Returns
        -------
            CompiledProgram object
        """
        self._core_scoper = ir.CoreScoper(self.ir_prog.scope, self._proc_grouping)
        asm_progs = {grp: [{'op': 'phase_reset'}] for grp in self._core_scoper.proc_groupings_flat}
        for blockname in self.ir_prog.blocknames_by_ind:
            self._compile_block(asm_progs, self.ir_prog.blocks[blockname]['instructions'])

        for proc_group in self._core_scoper.proc_groupings_flat:
            asm_progs[proc_group].append({'op': 'done_stb'})

        return CompiledProgram(asm_progs)

    def _compile_block(self, asm_progs, instructions):
        proc_groups_bydest = self._core_scoper.proc_groupings
        # TODO: add twidth attribute to env, not pulse
        for i, instr in enumerate(instructions):
            if instr.name == 'pulse':
                proc_group = proc_groups_bydest[instr.dest]

                if isinstance(instr.env, dict):
                    env = instr.env
                elif isinstance(instr.env[0], dict):
                    env = instr.env[0]
                    if len(instr.env) > 1:
                        logging.getLogger(__name__).warning(f'Only first env paradict {env} is being used')
                else:
                    env = instr.env

                if isinstance(env, dict):
                    if 'twidth' not in env['paradict'].keys():
                        env = copy.deepcopy(env)
                        env['paradict']['twidth'] = instr.twidth
                    elif env['paradict']['twidth'] != instr.twidth:
                        raise Exception('Pulse twidth differs from envelope!')

                asm_instr = {'op': 'pulse', 'freq': instr.freq, 'phase': instr.phase, 'amp': instr.amp,
                         'env': env, 'start_time': instr.start_time, 'dest': instr.dest}

                if instr.tag is not None:
                    asm_instr['tag'] = instr.tag

                asm_progs[proc_group].append(asm_instr)

            elif instr.name == 'jump_label':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'jump_label', 'dest_label': instr.label})

            elif instr.name == 'declare':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    if instr.dtype == 'phase' or instr.dtype == 'amp':
                        instr.dtype = (instr.dtype, 0)
                    asm_progs[core].append({'op': 'declare_reg', 'name': instr.var, 'dtype': instr.dtype})

            elif instr.name == 'alu':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'reg_alu', 'in0': instr.lhs, 'in1_reg': instr.rhs, 
                                                      'alu_op': instr.op, 'out_reg': instr.out})

            elif instr.name == 'set_var':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'reg_alu', 'in0': instr.value, 'in1_reg': instr.var,
                                            'alu_op': 'id0', 'out_reg': instr.var})
            elif instr.name == 'read_fproc':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'alu_fproc', 'in0': 0, 'alu_op': 'id1', 
                             'func_id': instr.func_id, 'out_reg': instr.var})

            elif instr.name == 'alu_fproc':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'alu_fproc', 'in0': instr.lhs, 'alu_op': instr.op, 
                             'func_id': instr.func_id, 'out_reg': instr.out})

            elif instr.name == 'jump_fproc':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'jump_fproc', 'in0': instr.cond_lhs, 'alu_op': instr.alu_cond, 
                             'jump_label': instr.jump_label, 'func_id': instr.func_id})

            elif instr.name == 'jump_cond':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'jump_cond', 'in0': instr.cond_lhs, 'alu_op': instr.alu_cond, 
                             'jump_label': instr.jump_label, 'in1_reg': instr.cond_rhs})

            elif instr.name == 'jump_i':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'jump_i', 'jump_label': instr.jump_label})

            elif instr.name == 'loop_end':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'inc_qclk', 'in0': -self.ir_prog.loops[instr.loop_label].delta_t})

            elif instr.name == 'idle':
                for core in self._core_scoper.get_groups_bydest(instr.scope):
                    asm_progs[core].append({'op': 'idle', 'end_time': instr.end_time})

            else:
                raise Exception(f'{instr.name} not yet implemented')

    def _resolve_duplicate_jumps(self):
        #todo: write method to deal with multiple jump labels in a row
        pass


@define
class CompiledProgram:
    """
    Simple class for reading/writing compiler output.

    Attributes:
        program : dict
            keys : proc group tuples (e.g. ('Q0.qdrv', 'Q0.rdrv', 'Q0.rdlo'))
                this is a tuple of channels that are driven by that proc core
            values : assembly program for corresponding proc core, in the format
                specified at the top of assembler.py. 

                NOTE: there is one deviation from this format; pulse commands 
                have a 'dest' field indicating the pulse channel, instead of
                an 'elem_ind'

        proc groups : list of proc group tuples

    TODO: metadata to consider adding:
        qchip version?
        git revision?
    """

    program: dict
    fpga_config: hw.FPGAConfig = None

    @property
    def proc_groups(self):
        return self.program.keys()

    def save(self, filename):
        progdict = copy.deepcopy(self.program)
        if self.fpga_config is not None:
            progdict['fpga_config'] = self.fpga_config.__dict__

        with open(filename) as f:
            json.dumps(progdict, f, indent=4)


def load_compiled_program(filename):
    with open(filename) as f:
        progdict = json.load(f)

    raise NotImplementedError
    return hw.FPGAConfig(**progdict['fpga_config'])


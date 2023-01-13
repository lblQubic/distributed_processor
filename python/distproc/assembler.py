"""
Distributed processor assembly language definition:
    list of dicts; should map 1-to-1 to assembled commands that run on proc

    pulse cmd:
        {'op': 'pulse', 'freq': <freq_in_Hz, regname>, 'env': <np_array, dict, regname>, 'phase': <phaserad, regname>,
            'amp': <float (normalized to 1), regname>, 'start_time': <starttime_in_clks>, 'elem_ind': <int>, 'label':<string>} 
            #todo: should elem_ind be replaced by chan name/string?
    reg_alu instructions:
        {'op': 'reg_alu', 'in0': <int, regname>, 'alu_op': alu_opcode_str, 'in1_reg': regname, 'out_reg': out_regname, 'label':<string>}
    inc_qclk:
        {'op': 'inc_qclk', 'in0': <int, regname>}
    jump_cond:
        {'op': 'jump_cond', 'in0': <int, regname>, 'alu_op': alu_opcode_str, 'in1_reg': regname, 'jump_label': <string>, 'label':<string>}
    jump_fproc:
        {'op': 'jump_fproc', 'in0': <int, regname>, 'alu_op': alu_op, 'jump_label': jump_label, 'func_id': func_id}
    reg_write:
        {'op': 'reg_write', 'value': <int>, 'reg_name': out_regname, 'label':<string>} 
        note: this is just a helper/wrapper for a reg_alu instruction
    other:
        {'op': 'phase_reset'}
        {'op': 'done_stb'}

"""

import distproc.command_gen as cg
import copy
import numpy as np
import ipdb
import distproc.hwconfig as hw
from collections import OrderedDict
import warnings

ENV_BITS = 16
N_MAX_REGS = 16

class SingleCoreAssembler:
    """
    Class for constructing an assembly-language level program and 
    converting to machine code + env buffers. Program can be constructed
    dynamically using the provided functions or specified/read from text file
    as a list of dictionaries (format at the beginning of this file)
    
    TODO: Consider replacing add_reg_write, etc with alu_cmd instruction
    similar to command_gen

    Attributes
    ----------
        _regs : dict
            key: user-declared register name
            value: register address in proc core
    """
    def __init__(self, elem_cfgs):
        self.n_element = len(elem_cfgs)
        self._env_dicts = [OrderedDict() for i in range(self.n_element)] #map names to envelope
        self._freq_lists = [[] for i in range(self.n_element)] #map inds to freq
        self._program = []
        self._regs = {}
        self._elem_cfgs = elem_cfgs

    def from_list(self, cmd_list):
        for cmd in cmd_list:
            cmdargs = cmd.copy()
            del cmdargs['op']
            if cmd['op'] == 'pulse':
                nreg_params = np.sum([isinstance(cmd[key], str) for key in ['freq', 'amp', 'phase']])
                if nreg_params > 1:
                    warnings.warn('{} will be split into multiple instructions, which may cause timing problems'.format(cmd))
                self.add_pulse(**cmdargs)
            elif cmd['op'] in ['reg_alu', 'jump_cond', 'alu_fproc', 'jump_fproc', 'inc_qclk']:
                self.add_alu_cmd(**cmd)
            elif cmd['op'] == 'reg_write':
                self.add_reg_write(**cmdargs)
            elif cmd['op'] == 'phase_reset':
                self.add_phase_reset(**cmdargs)
            elif cmd['op'] == 'done_stb':
                self.add_done_stb(**cmdargs)
            else:
                raise Exception('{} not supported!'.format(cmd))

    def add_alu_cmd(self, op, in0, alu_op, in1_reg=None, out_reg=None, jump_label=None, fproc_id=None, label=None):
        assert op in ['reg_alu', 'jump_cond', 'alu_fproc', 'jump_fproc', 'inc_qclk']
        assert in1_reg in self._regs.keys()
        if isinstance(in0, str):
            assert in0 in self._regs.keys()

        cmd = {'op' : op, 'in0' : in0, 'alu_op' : alu_op}

        if op in ['reg_alu', 'jump_cond']:
            assert in1_reg is not None
            assert fproc_id is None
            cmd['in1_reg'] = in1_reg
        else:
            assert in1_reg is None

        if op in ['reg_alu', 'alu_fproc']:
            assert out_reg is not None
            if out_reg not in self._regs.keys():
                self.declare_reg(out_reg)
            cmd['out_reg'] = out_reg
        else:
            assert out_reg is None

        if op in ['jump_cond', 'jump_fproc']:
            assert jump_label is not None
            cmd['jump_label'] = jump_label

        if op in ['alu_fproc', 'jump_fproc']: #None defaults to 0, implies fproc_id not used
            cmd['fproc_id'] = fproc_id
        else:
            assert fproc_id is None

        if label is not None:
            cmd['label'] = label

        self._program.append(cmd)

    def add_env(self, name, env, elem_ind):
        if np.any(np.abs(env) > 1):
            raise Exception('env mag must be < 1')
        self._env_dicts[elem_ind][name] = env

    def add_freq(self, freq, elem_ind, freq_ind=None):
        if freq_ind is None:
            self._freq_lists[elem_ind].append(freq)
        elif freq_ind >= len(self._freq_lists[elem_ind]):
            for i in range(len(self._freq_lists[elem_ind]) - freq_ind):
                self._freq_lists[elem_ind].append(None)
            self._freq_lists[elem_ind].append(freq)
        else:
            if self._freq_lists[elem_ind][freq_ind] is None:
                raise ValueError('ind {} is already occupied!'.format(freq_ind))
            self._freq_lists[elem_ind][freq_ind] = freq

    def declare_reg(self, name):
        """
        Declare a named register that can be referenced 
        by subsequent commands
        """
        if not self._regs:
            self._regs[name] = 0
        elif 'name' in self._regs.keys():
            raise Exception('Register already declared!') #maybe make this a warning?
        else:
            max_regind = max(self._regs.values())
            if max_regind >= N_MAX_REGS - 1:
                raise Exception('cannot add any more regs, limit of {} reached'.format(N_MAX_REGS))
            self._regs[name] = max_regind + 1

    def add_reg_write(self, reg_name, value, label=None):
        """
        Write 'value' to a named register reg_name. CAN be declared implicitly.
        """
        if reg_name not in self._regs.keys():
            self.declare_reg(reg_name)
        self.add_reg_alu(value, 'id0', reg_name, reg_name, label)

    def add_reg_alu(self, in0, alu_op, in1_reg, out_reg, label=None):
        """
        Add a command for an ALU operation on registers.

        Parameters
        ----------
            in0 : int or str
                First input to ALU. If int, assumed to be intermediate value. If string,
                assumed to be named register
            alu_op : str
                'add', 'sub', 'id0', 'id1', 'eq', 'le', 'ge', 'zero'
            in1_reg : str
                Second input to ALU. Named register
            out_reg : str
                Reg that gets written w/ ALU output. CAN be declared implicitly.
        """
        self.add_alu_cmd('reg_alu', in0, alu_op, in1_reg, out_reg, label=label)

    def add_phase_reset(self, label=None):
        cmd = {'op': 'pulse_reset'}
        if label is not None:
            cmd['label'] = label
        self._program.append(cmd)

    def add_done_stb(self, label=None):
        cmd = {'op': 'done_stb'}
        if label is not None:
            cmd['label'] = label
        self._program.append(cmd)

    def add_jump_cond(self, in0, alu_op, in1_reg, jump_label, label=None):
        self.add_alu_cmd('jump_cond', in0, alu_op, in1_reg, jump_label=jump_label, label=label)

    def add_inc_qclk(self, increment, label=None):
        self.add_alu_cmd('inc_qclk', increment, 'add', label=label)

    def add_jump_fproc(self, in0, alu_op, jump_label, func_id=None, label=None):
        self.add_alu_cmd('jump_fproc', in0, alu_op, jump_label=jump_label, func_id=func_id, label=label)

    def add_pulse(self, freq, phase, amp, start_time, env, elem_ind, length=None, label=None):
        """
        Add a pulse command to the program. 'freq' and 'phase' can be specified by 
        named registers or immediate values.

        Parameters
        ----------
            freq : float, int, str
                If numerical, pulse frequency in Hz; if string, named register
                to use. Register must be declared beforehand.
            phase : float, str
                If numerical, pulse phase in radians; if string, named register
                to use. Register must be declared beforehand.
            env : np.ndarray, str
                Either an array of envelope samples, or a string specifying 
                named envelope to use. Envelope array is hashed to see if it's 
                already been added. Note: doesn't work with user added named envelopes
            length : int
                pulse length in samples. If None, use len(env)
            label : str
                label for this program instruction. Useful (required) for jumps.
        """
        if isinstance(env, np.ndarray): 
            if np.any((np.abs(np.real(env)) > 1) | (np.abs(np.imag(env)) > 1)):
                raise Exception('env must be < 1')
            envkey = self._hash_env(env)
            if envkey not in self._env_dicts[elem_ind]:
                self._env_dicts[elem_ind][envkey] = env
        elif isinstance(env, str):
            envkey = env
        else:
            raise Exception('env must be string or np array')
        
        if length is not None:
            if length > len(self._env_dicts[elem_ind][envkey]):
                raise Exception('provided pulse length exceeds length of envelope')
            elif length < len(self._env_dicts[elem_ind][envkey]) and length % self._elem_cfgs[elem_ind].samples_per_clk != 0:
                raise Exception('env length must match pulse length if end of pulse is not aligned with clock boundary') 
        else:
            length = len(self._env_dicts[elem_ind][envkey])

        if isinstance(freq, str):
            assert freq in self._regs.keys()
        else:
            if freq not in self._freq_lists[elem_ind]: #if freq is numerical, add to list of freqs
                self.add_freq(freq, elem_ind)

        if isinstance(amp, str):
            assert amp in self._regs.keys()

        if isinstance(phase, str):
            assert phase in self._regs.keys()

        if isinstance(freq, str) and isisnstance(phase, str) and isinstance(amp, str):
            #can only do one pulse_reg write at a time so use two instructions
            self._program.append({'op': 'pulse', 'freq': freq})
            self._program.append({'op': 'pulse', 'amp': amp})
            cmd = {'op': 'pulse', 'phase': phase, 'start_time': start_time, 'length': length, 'env': envkey, 'elem': elem_ind}
        elif isinstance(freq, str) and (isinstance(phase, str) or isinstance(amp, str)):
            self._program.append({'op': 'pulse', 'freq': freq})
            cmd = {'op': 'pulse', 'phase': phase, 'amp': amp, 'start_time': start_time, 'length': length, 'env': envkey, 'elem': elem_ind}
        elif isinstance(phase, str) and isinstance(amp, str):
            self._program.append({'op': 'pulse', 'freq': phase})
            cmd = {'op': 'pulse', 'freq': freq, 'amp': amp, 'start_time': start_time, 'length': length, 'env': envkey, 'elem': elem_ind}
        else:
            cmd = {'op': 'pulse', 'freq': freq, 'phase': phase, 'amp': amp, 'start_time': start_time, 'length': length, 'env': envkey, 'elem': elem_ind}

        if label is not None:
            cmd['label'] = label
        self._program.append(cmd)

    def get_compiled_program(self):
        cmd_list = []
        freq_list = []
        env_raw, env_ind_map = self._get_env_buffers()
        cmd_label_addrmap = self._get_cmd_labelmap()
        freq_raw, freq_ind_map = self._get_freq_buffers()
        for cmd in self._program:
            cmd = copy.deepcopy(cmd) #we are modifying cmd so don't overwrite anything in self._program

            if cmd['op'] == 'pulse':
                pulseargs = {}

                if 'freq' in cmd.keys():
                    if isinstance(cmd['freq'], str):
                        pulseargs['freq_regaddr'] = self._regs[cmd['freq']]
                    else:
                        pulseargs['freq_word'] = self._elem_cfgs[cmd['elem']].get_freq_addr(freq_ind_map[cmd['elem']][cmd['freq']])

                if 'phase' in cmd.keys():
                    if isinstance(cmd['phase'], str):
                        pulseargs['phase_regaddr'] = self._regs[cmd['phase']]
                    else:
                        pulseargs['phase_word'] = self._elem_cfgs[cmd['elem']].get_phase_word(cmd['phase'])

                if 'amp' in cmd.keys():
                    if isinstance(cmd['amp'], str):
                        pulseargs['amp_regaddr'] = self._regs[cmd['amp']]
                    else:
                        pulseargs['amp_word'] = self._elem_cfgs[cmd['elem']].get_amp_word(cmd['amp'])

                if 'env' in cmd.keys():
                    pulseargs['env_word'] = self._elem_cfgs[cmd['elem']].get_env_word(env_ind_map[cmd['elem']][cmd['env']], cmd['length'])

                if 'start_time' in cmd.keys():
                    pulseargs['cmd_time'] = cmd['start_time']

                if 'elem' in cmd.keys():
                    pulseargs['cfg_word'] = self._elem_cfgs[cmd['elem']].get_cfg_word(cmd['elem'], None)
                    
                cmd_list.append(cg.pulse_cmd(**pulseargs))

            elif cmd['op'] in ['reg_alu', 'jump_cond', 'alu_fproc', 'jump_fproc', 'inc_qclk']:
                if isinstance(cmd['in0'], str):
                    in0 = self._regs[cmd['in0']]
                    im_or_reg = 'r'
                else:
                    in0 = cmd['in0']
                    im_or_reg = 'i'

                if 'out_reg' in cmd.keys():
                    cmd['out_reg'] = self._regs[cmd['out_reg']]

                if 'jump_label' in cmd.keys():
                    cmd['jump_addr'] = cmd_label_addrmap[cmd['jump_label']]

                if 'in1_reg' in cmd.keys():
                    cmd['in1_reg'] = self._regs[cmd['in1_reg']]

                cmd_list.append(cg.alu_cmd(cmd['op'], im_or_reg, in0, cmd.get('alu_op'), \
                        cmd.get('in1_reg'), cmd.get('out_reg'), cmd.get('jump_addr'), cmd.get('func_id')))

            elif cmd['op'] == 'pulse_reset':
                cmd_list.append(cg.pulse_reset())

            elif cmd['op'] == 'done_stb':
                cmd_list.append(cg.done_cmd())

            else:
                raise Exception('{} not supported'.format(cmd['op']))

        return cmd_list, env_raw, freq_raw
    
    def get_sim_program(self):
        """
        Get a pulse/command list usable by simulation tools. Currently, this is the same as 
        self._program, but with env names replaced by data
        """
        cmd_list = []
        for cmd in self._program:
            cmd = copy.deepcopy(cmd)
            if cmd['op'] == 'pulse':
                cmd.update({'env':self._env_dicts[cmd['elem']][cmd['env']]})
            cmd_list.append(cmd)

        return cmd_list

    def _get_cmd_labelmap(self):
        """
        Get command locations (addresses) for labeled commands. 
        Used for jump instructions
        """
        labelmap = {}
        for i, cmd in enumerate(self._program):
            if 'label' in cmd.keys():
                labelmap[cmd['label']] = i
        return labelmap

    def _get_env_buffer(self, elem_ind):
        """
        Computes the raw envelope buffer along with a dictionary of indices. Address
        is computed later by hwconfig

        Returns
        -------
            env_raw : np.ndarray
                numpy array of the raw envelope buffer. Each element is a 
                32-bit word, with a signed 16-bit I value LSB followed by
                a signed 16-bit Q value MSB
            env_addr_map : dict
                dictionary of envelope addresses, to be used by pulse commands.
                Keys are the same as used by self._env_dict.
                The process element hardware module (element.v) has four separate
                memory banks for the envelope, with one output value per-clock 
                (so 4x250 MHz = 1 GHz). Addresses index these buffers, so 
                the address here is the envelope start index in env_raw divided
                by four.
        """
        cur_env_ind = 0
        env_ind_map = {}

        env_raw = np.empty(0).astype(int)

        for envkey, env in self._env_dicts[elem_ind].items():
            env_ind_map[envkey] = cur_env_ind
            env = self._elem_cfgs[elem_ind].get_env_buffer(env)
            cur_env_ind += len(env)
            env_raw = np.append(env_raw, env)

        return env_raw, env_ind_map
    
    def _get_env_buffers(self):
        env_data = []
        env_ind_maps = []
        for i in range(self.n_element):
            d, m = self._get_env_buffer(i)
            env_data.append(d)
            env_ind_maps.append(m)

        return env_data, env_ind_maps

    def _get_freq_buffer(self, elem_ind):
        """
        Return the full raw freq buffer + index map
        """
        freq_buffer = self._elem_cfgs[elem_ind].get_freq_buffer(self._freq_lists[elem_ind])
        freq_ind_map = {f: self._freq_lists[elem_ind].index(f) for f in self._freq_lists[elem_ind]}
        return freq_buffer, freq_ind_map

    def _get_freq_buffers(self):
        freq_data = []
        freq_ind_maps = []
        for i in range(self.n_element):
            d, m = self._get_freq_buffer(i)
            freq_data.append(d)
            freq_ind_maps.append(m)

        return freq_data, freq_ind_maps


    def _hash_env(self, env):
        return str(hash(env.data.tobytes()))


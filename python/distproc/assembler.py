import distproc.command_gen as cg
import copy
import numpy as np
import ipdb

ENV_BITS = 16
N_MAX_REGS = 16

class MultiUnitAssembler:

    def __init__(self, n_units):
        self.n_units = n_units
        self.assemblers = []
        for i in range(self.n_units):
            self.assemblers.append(SingleUnitAssembler())

    def add_env(self, unitind, name, env):
        self.assemblers[unitind].add_env(name, env)

    def add_pulse(self, unitind, freq, phase, start_time, env, length=None, label=None):
        self.assemblers[unitind].add_pulse(freq, phase, start_time, env, length, label)

    def get_compiled_program(self):
        cmd_lists = []
        env_buffers = []
        for assembler in self.assemblers:
            cmd_list, env_raw = assembler.get_compiled_program()
            cmd_lists.append(cmd_list)
            env_buffers.append(env_raw)

        return cmd_lists, env_buffers

    def get_sim_program(self):
        prog = []
        for assembler in self.assemblers:
            prog.append(assembler.get_sim_program())

        return prog

class SingleUnitAssembler:
    """
    Class for constructing an assembly-language level program and 
    converting to machine code + env buffers
    Attributes
    ----------
        _regs : dict
            key: user-declared register name
            value: register address in proc core
    """
    def __init__(self):
        self._env_dict = {}
        self._program = []
        self._regs = {}

    def add_env(self, name, env):
        if np.any(np.abs(env) > 1):
            raise Exception('env mag must be < 1')
        self._env_dict[name] = env

    def declare_reg(self, name):
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
        assert in1_reg in self._regs.keys()
        if isinstance(in0, str):
            assert in0 in self._regs.keys()

        if out_reg not in self._regs.keys():
            self.declare_reg(out_reg)

        cmd = {'cmdtype': 'reg_alu', 'in0': in0, 'alu_op': alu_op, 'in1_reg': in1_reg, 'out_reg': out_reg}
        if label is not None:
            cmd['label'] = label
        self._program.append(cmd)

    def add_jump_cond(self, in0, alu_op, in1_reg, jump_label, label=None):
        assert in1_reg in self._regs.keys()
        if isinstance(in0, str):
            assert in0 in self._regs.keys()

        cmd = {'cmdtype': 'jump_cond', 'in0': in0, 'alu_op': alu_op, 'in1_reg': in1_reg, 'jump_label': jump_label}
        if label is not None:
            cmd['label'] = label
        self._program.append(cmd)

    def add_jump_fproc(self, in0, alu_op, jump_label, func_id=None, label=None):
        if isinstance(in0, str):
            assert in0 in self._regs.keys()
        cmd = {'cmdtype': 'jump_fproc', 'in0': in0, 'alu_op': alu_op, 'jump_label': jump_label, 'func_id': func_id}
        if label is not None:
            cmd['label'] = label
        self._program.append(cmd)

    def add_pulse(self, freq, phase, start_time, env, length=None, label=None):
        #hash the envelope to see if it's already been added
        # note: doesn't work with user added named envelopes
        if isinstance(env, np.ndarray): 
            if np.any((np.abs(np.real(env)) > 1) | (np.abs(np.imag(env)) > 1)):
                raise Exception('env must be < 1')
            envkey = self._hash_env(env)
            if envkey not in self._env_dict:
                self._env_dict[envkey] = env
        elif isinstance(env, str):
            envkey = env
        else:
            raise Exception('env must be string or np array')

        if length is not None:
            if length > len(self._env_dict[envkey]):
                raise Exception('provided pulse length exceeds length of envelope')
            elif length < len(self._env_dict[envkey]) and length % 4 != 0:
                raise Exception('env length must match pulse length if end of pulse is not aligned with clock boundary') 
        else:
            length = len(self._env_dict[envkey])

        cmd = {'cmdtype': 'pulse', 'freq': freq, 'phase': phase, 'start_time': start_time, 'length': length, 'env': envkey}
        if label is not None:
            cmd['label'] = label
        self._program.append(cmd)

    def get_compiled_program(self):
        cmd_list = []
        env_raw, env_addr_map = self._get_env_buffer()
        cmd_label_addrmap = self._get_cmd_labelmap()
        for cmd in self._program:
            if cmd['cmdtype'] == 'pulse':
                length = int(4*np.ceil(cmd['length']/4)) #quantize pulse length to multiple of 4
                cmd_list.append(cg.pulse_i(cmd['freq'], cmd['phase'], \
                        env_addr_map[cmd['env']], length, cmd['start_time']))
            elif cmd['cmdtype'] in ['reg_alu', 'jump_cond', 'alu_fproc', 'jump_fproc', 'inc_qclk']:
                if isinstance(cmd['in0'], str):
                    in0 = self._regs[cmd['in0']]
                    im_or_reg = 'r'
                else:
                    in0 = cmd['in0']
                    im_or_reg = 'i'

                if 'out_reg' in cmd.keys():
                    write_reg_addr = self._regs[cmd['out_reg']]
                else:
                    write_reg_addr = None

                if 'jump_label' in cmd.keys():
                    jump_addr = cmd_label_addrmap[cmd['jump_label']]
                else:
                    jump_addr = None 

                if 'in1_reg' in cmd.keys():
                    in1 = self._regs[cmd['in1_reg']]
                else:
                    in1 = None

                cmd_list.append(cg.alu_cmd(cmd['cmdtype'], im_or_reg, in0, cmd.get('alu_op', None), \
                        in1, write_reg_addr, jump_addr, cmd.get('func_id', None)))
            else:
                raise Exception('{} not supported'.format['cmdtype'])

        return cmd_list, env_raw
    
    def get_sim_program(self):
        """
        Get a pulse/command list usable by simulation tools. Currently, this is the same as 
        self._program, but with env names replaced by data
        """
        cmd_list = []
        for cmd in self._program:
            cmd = copy.deepcopy(cmd)
            if cmd['cmdtype'] == 'pulse':
                cmd.update({'env':self._env_dict[cmd['env']]})
            cmd_list.append(cmd)

        return cmd_list

    def _get_cmd_labelmap(self):
        labelmap = {}
        for i, cmd in enumerate(self._program):
            if 'label' in cmd.keys():
                labelmap[cmd['label']] = i
        return labelmap

    def _get_env_buffer(self):
        """
        Computes the raw envelope buffer along with a dictionary of addresses

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
        cur_addr = 0
        env_addr_map = {}

        env_raw = np.empty(0).astype(int)

        for envkey, env in self._env_dict.items():
            #ipdb.set_trace()
            env_addr_map[envkey] = cur_addr
            env = np.pad(env, (0, (4 - len(env) % 4) % 4))
            cur_addr += len(env)//4

            env_val = cg.twos_complement(np.real(env*2**(ENV_BITS-1)).astype(int), nbits=ENV_BITS) \
                        + (cg.twos_complement(np.imag(env*2**(ENV_BITS-1)).astype(int), nbits=ENV_BITS) << ENV_BITS)
            env_raw = np.append(env_raw, env_val)

        return env_raw, env_addr_map
            
    def _hash_env(self, env):
        return str(hash(env.data.tobytes()))

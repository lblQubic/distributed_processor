import distproc.command_gen as cg
import copy
import numpy as np
import ipdb

ENV_BITS = 16

class SingleUnitAssembler:

    def __init__(self):
        self._env_dict = {}
        self._program = []

    def add_env(self, name, env):
        if np.any(np.real(env) > 1 or np.imag(env) > 1):
            raise Exception('env must be < 1')
        self._env_dict[name] = env

    def add_pulse(self, freq, phase, start_time, env, length=None):
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
        self._program.append({'freq': freq, 'phase': phase, 'start_time': start_time, 'length': length, 'env': envkey})

    def get_compiled_program(self):
        cmd_list = []
        env_raw, env_addr_map = self._get_env_buffer()
        for pulse in self._program:
            length = int(4*np.ceil(pulse['length']/4)) #quantize pulse length to multiple of 4
            cmd_list.append(cg.pulse_i(pulse['freq'], pulse['phase'], env_addr_map[pulse['env']], length, pulse['start_time']))

        return cmd_list, env_raw
    
    def get_sim_program(self):
        """
        Get a pulse/command list usable by simulation tools. Currently, this is the same as 
        self._program, but with env names replaced by data
        """
        pulse_list = []
        for pulse in self._program:
            pulse = copy.deepcopy(pulse)
            pulse.update({'env':self._env_dict[pulse['env']]})
            pulse_list.append(pulse)

        return pulse_list

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


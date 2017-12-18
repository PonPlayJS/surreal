"""
Agent side.
Send experience chunks (buffered) to Replay node.
"""
import surreal.utils as U
from surreal.session import PeriodicTracker
from .zmq_struct import ZmqPushClient


class ExpBuffer(object):
    def __init__(self):
        self.exp_list = []  # list of exp dicts
        self.ob_storage = {}

    def add(self, hash_dict, nonhash_dict):
        """
        Args:
            hash_dict: {obs_hash: [ .. can be nested .. ]}
            nonhash_dict: {reward: -1.2, done: True, ...}
        """
        U.assert_type(hash_dict, dict)
        U.assert_type(nonhash_dict, dict)
        exp = {}
        for key, values in hash_dict.items():
            assert not key.endswith('_hash'), 'do not manually append `_hash`'
            exp[key + '_hash'] = self._hash_nested(values)
        exp.update(nonhash_dict)
        self.exp_list.append(exp)

    def flush(self):
        binary = U.serialize((self.exp_list, self.ob_storage))
        # U.print_('SIZE', len(binary), 'Exp', self.exp_tuples, 'ob', self.ob_storage)
        self.exp_list = []
        self.ob_storage = {}
        return binary

    def _hash_nested(self, values):
        if isinstance(values, list):
            return [self._hash_nested(v) for v in values]
        elif isinstance(values, dict):
            return {k: self._hash_nested(v) for k, v in values.items()}
        else:  # values is a single object
            obj = values
            hsh = U.pyobj_hash(obj)
            if hsh not in self.ob_storage:
                self.ob_storage[hsh] = obj
            return hsh


class ExpSender(object):
    """
    `send()` logic can be overwritten to support more complicated agent experiences,
    such as multiagent, self-play, etc.
    """
    def __init__(self, *,
                 host,
                 port,
                 # TODO add flush_time
                 flush_iteration):
        """
        Args:
            flush_iteration: how many send() calls before we flush the buffer
        """
        U.assert_type(flush_iteration, int)
        self._client = ZmqPushClient(
            host=host,
            port=port,
            is_pyobj=False,
        )
        self._exp_buffer = ExpBuffer()
        self._flush_tracker = PeriodicTracker(flush_iteration)

    def send(self, hash_dict, nonhash_dict):
        """
            TODO: Jim should add some comment on how hash_dict and nonhash_dict works
        """
        self._exp_buffer.add(
            hash_dict=hash_dict, 
            nonhash_dict=nonhash_dict,
        )
        if self._flush_tracker.track_increment():
            exp_binary = self._exp_buffer.flush()
            self._client.push(exp_binary)
            return U.binary_hash(exp_binary)
        else:
            return None

# class ExpSender(ExpSenderBase):
#     # I suggest deprecating this class and make every exp sender wrapper use the same ExpSenderBase
#     # So custom logic of sending experience goes with the wrapper that can be defined by environment
#     # and exp_sender is just a infrastructure layer
#     # Currently I am keeping it for backward compatibility 
#     """
#     `send()` logic can be overwritten to support more complicated agent experiences,
#     such as multiagent, self-play, etc.
#     """
#     def send(self, obs, action, reward, done, info):
#         """
#             Pack observations into compressed format
#             Keep others in normal format
#         """
#         hash_dict = {
#             'obs': obs
#         }
#         nonhash_dict = {
#             'action': action,
#             'reward': reward,
#             'done': done,
#             'info': info
#         }
#         return super().send(hash_dict, nonhash_dict)
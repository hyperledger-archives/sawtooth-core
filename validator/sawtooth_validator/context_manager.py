# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------
import hashlib
import logging
import time

from threading import Thread
from threading import Lock
from threading import Condition
from queue import Queue

from sawtooth_validator.merkle import MerkleDatabase


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)


class AuthorizationException(Exception):
    def __init__(self, address):
        super(AuthorizationException, self).__init__(
            "Not authorized to read/write to {}".format(address))


class CommitException(Exception):
    pass


class SquashException(Exception):
    pass


class StateContext(object):
    """
    Attributes:
        self._state_hash (str):
        self._read_list (list):
        self._write_list (list):
        self._address_value_dict (dict): a dict with address keys and
                                    _ContextFuture values
    """
    def __init__(self, state_hash, read_list, write_list):
        """

        Args:
            state_hash: the Merkle root
            access_list: a list of tuples ('read', address)...
        """
        self._state_hash = state_hash

        self._read_list = read_list
        self._write_list = write_list

        self._address_value_dict = {}

        self._id = hashlib.sha256((str(state_hash) + ":" +
                                  str(read_list + write_list) + ":" +
                                  str(time.time())).encode()).hexdigest()

    @property
    def session_id(self):
        return self._id

    @property
    def merkle_root(self):
        return self._state_hash

    def initialize_futures(self, address_list):
        """

        Args:
            address_list (list): a list of addresses

        Returns: void

        """
        for add in address_list:
            self._address_value_dict[add] = _ContextFuture(add)

    def set_futures(self, address_value_dict):
        for add, val in address_value_dict.items():
            context_future = self._address_value_dict.get(add)
            context_future.set_result(val)

    def get_writable_address_value_dict(self):
        add_value_dict = {}
        for add, val in self._address_value_dict.items():
            if add in self._write_list:
                add_value_dict[add] = val
        return add_value_dict

    def get_address_value_dict(self):
        return self._address_value_dict

    def get_from_prefetched(self, address_list):
        """

        Args:
            address_list (list): a list of addresses

        Returns:
            found_values (list): a list of (address, ContextFuture) tuples

        """
        found_values = []
        for address in address_list:
            if address not in self._read_list:
                LOGGER.warning("Authorization exception, address: %s", address)
                raise AuthorizationException(address)
            found_values.append((address,
                                self._address_value_dict.get(address)))
        return found_values

    def can_set(self, address_value_list):
        for add_value_dict in address_value_list:
            for address in add_value_dict.keys():
                if address not in self._write_list:
                    raise AuthorizationException(address)


class ContextManager(object):

    def __init__(self, database):
        """

        Args:
            database database.Database subclass: the subclass/implementation of
                                                the Database
        """
        self._database = database
        self._first_merkle_root = None
        self._contexts = {}

        self._address_queue = Queue()

        inflated_addresses = Queue()

        self._context_reader = _ContextReader(database, self._address_queue,
                                              inflated_addresses)
        self._context_reader.setDaemon(True)
        self._context_reader.start()

        # the lock is shared between the ContextManager and
        # the _ContextWriter because they both access _contexts
        self._shared_lock = Lock()
        self._context_writer = _ContextWriter(self._shared_lock,
                                              inflated_addresses,
                                              self._contexts)
        self._context_writer.setDaemon(True)
        self._context_writer.start()

    def get_first_root(self):
        if self._first_merkle_root is not None:
            return self._first_merkle_root
        self._first_merkle_root = MerkleDatabase(
            self._database).get_merkle_root()
        return self._first_merkle_root

    def create_context(self, state_hash, inputs, outputs):
        """
        Part of the interface to the Executor
        Args:
            state_hash: (str): Merkle root
            access_list: (list): list of tuples like [('read', 'address'),...

        Returns:
            context_id (str): the unique context_id of the session

        """
        context = StateContext(state_hash, inputs, outputs)
        with self._shared_lock:
            context.initialize_futures(inputs + outputs)
            self._contexts[context.session_id] = context

        self._address_queue.put_nowait(
            (context.session_id, state_hash, inputs))
        LOGGER.info("CREATE_CONTEXT: %s", context.session_id)
        return context.session_id

    def commit_context(self, context_id_list, virtual):
        """
        Part of the interface to the Executor
        Args:
            context_id_list:

        Returns:
            state_hash (str): the new state hash after the context_id_list
                              has been committed

        """

        if any([c_id not in self._contexts for c_id in context_id_list]):
            raise CommitException("Context Id not in contexts")
        first_id = context_id_list[0]

        if not all([self._contexts[first_id].merkle_root ==
                    self._contexts[c_id].merkle_root
                    for c_id in context_id_list]):
            raise CommitException(
                "MerkleRoots not all equal, yet asking to merge")

        merkle_root = self._contexts[first_id].merkle_root
        tree = MerkleDatabase(self._database, merkle_root)

        merged_updates = {}
        for c_id in context_id_list:
            with self._shared_lock:
                context = self._contexts[c_id]
                del self._contexts[c_id]
            for k in context.get_writable_address_value_dict().keys():
                if k in merged_updates:
                    raise CommitException(
                        "Duplicate address {} in context {}".format(k, c_id))
            merged_updates.update(context.get_writable_address_value_dict())

        new_root = merkle_root
        add_value_dict = {address: value.result()
                          for address, value in merged_updates.items()}
        new_root = tree.update(set_items=add_value_dict, virtual=virtual)

        return new_root

    def delete_context(self, context_id_list):
        """
        Part of the interface to the Executor.
        Throws away contexts, eg. InvalidTransaction
        Args:
            context_id_list (list): a list of context ids

        Returns:
            void

        """
        for c_id in context_id_list:
            with self._shared_lock:
                if c_id in self._contexts:
                    del self._contexts[c_id]

    def get(self, context_id, address_list):
        """

        Args:
            context_id (str): the return value of create_context
            address_list (list): a list of address strs

        Returns:
            values_list (list): a list of (address, value) tuples
        """
        with self._shared_lock:
            if context_id not in self._contexts:
                return []
        with self._shared_lock:
            context = self._contexts.get(context_id)
            return [(a, f.result())
                    for a, f in context.get_from_prefetched(address_list)]

    def set(self, context_id, address_value_list):
        """
        speculatively sets addresses to a value,
        can be destroyed or committed to the merkle store
        Args:
            context_id (str): the context id returned by create_context
            address_value_list (list): list of {address: value} dicts

        Returns (boolean): True, or False whether the

        """
        with self._shared_lock:
            if context_id not in self._contexts:
                LOGGER.info("Context_id not in contexts, %s", context_id)
                return False
        with self._shared_lock:
            context = self._contexts.get(context_id)
            context.can_set(address_value_list)
            add_value_dict = {}
            for d in address_value_list:
                for add, val in d.items():
                    add_value_dict[add] = val
            context.set_futures(add_value_dict)
        return True

    def get_squash_handler(self):
        def _squash(state_root, context_ids):
            tree = MerkleDatabase(self._database, state_root)
            updates = dict()
            for c_id in context_ids:
                context = self._contexts[c_id]
                if any([add in updates for add in
                        context.get_address_value_dict().keys()]):
                    raise SquashException(
                        "Address already in a context to be written to.")
                updates.update({k: v.result() for k, v in
                                context.get_address_value_dict().items()})
            state_hash = tree.update(updates, virtual=False)
            return state_hash
        return _squash

    def stop(self):
        self._context_writer.join(1)
        self._context_reader.join(1)


class _ContextReader(Thread):
    """
    Attributes:
        _in_condition (threading.Condition): threading object for notification
        _addresses (queue.Queue): each item is a tuple
                                  (context_id, state_hash, address_list)
        _inflated_addresses (queue.Queue): each item is a tuple
                                          (context_id, [(address, value), ...
    """
    def __init__(self, database, address_queue, inflated_addresses):
        super(_ContextReader, self).__init__()
        self._database = database
        self._addresses = address_queue
        self._inflated_addresses = inflated_addresses

    def run(self):
        while True:
            context_state_addresslist_tuple = self._addresses.get(block=True)
            c_id, state_hash, address_list = context_state_addresslist_tuple
            tree = MerkleDatabase(self._database, state_hash)
            return_values = []
            for address in address_list:
                value = None
                try:
                    value = tree.get(address)
                except KeyError:
                    pass
                return_values.append((address, value))
            self._inflated_addresses.put((c_id, return_values))


class _ContextWriter(Thread):
    """
    Attributes:
        _condition (threading.Condition): threading object for notification
        _inflated_addresses (queue.Queue): each item is a tuple
                                           (context_id, [(address, value), ...
    """

    def __init__(self, lock, inflated_addresses, contexts):
        super(_ContextWriter, self).__init__()
        self._lock = lock
        self._inflated_addresses = inflated_addresses

        self._contexts = contexts

    def run(self):
        while True:
            c_id, inflated_address_list = self._inflated_addresses.get(
                block=True)
            with self._lock:
                if c_id in self._contexts:
                    self._contexts[c_id].set_futures(
                        {k: v for k, v in inflated_address_list})


class _ContextFuture(object):
    def __init__(self, address):
        self.address = address
        self._result = None
        self._result_is_set = False
        self._condition = Condition()

    def done(self):
        return self._result_is_set

    def result(self):
        with self._condition:
            if not self._result_is_set:
                self._condition.wait(2)
        return self._result

    def set_result(self, result):
        with self._condition:
            self._result = result
            self._result_is_set = True
            self._condition.notify()

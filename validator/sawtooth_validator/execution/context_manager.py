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
import uuid

from threading import Condition
from threading import Lock
from threading import Thread
from queue import Queue

from sawtooth_validator.state.merkle import MerkleDatabase


LOGGER = logging.getLogger(__name__)


class AuthorizationException(Exception):
    def __init__(self, address):
        super(AuthorizationException, self).__init__(
            "Not authorized to read/write to {}".format(address))


class CommitException(Exception):
    pass


class SquashException(Exception):
    pass


_SHUTDOWN_SENTINEL = -1


class StateContext(object):
    """A data structure holding address-_ContextFuture pairs and the addresses
    that can be written to and read from.
    """
    def __init__(self, state_hash, read_list, write_list, base_context_ids):
        """

        Args:
            state_hash: the Merkle root
            read_list (list of str): Addresses that were listed as inputs on
                the transaction.
            write_list (list of str): Addresses that were listed as outputs on
                the transaction.
            base_context_ids (list of str): Context ids of contexts that this
                context is based off of.
        """
        self._state_hash = state_hash

        self._read_list = set(read_list)
        self._write_list = set(write_list)

        self._state = {}
        self.base_context_ids = base_context_ids

        self._id = hashlib.sha256(uuid.uuid4().hex.encode()).hexdigest()

    @property
    def session_id(self):
        return self._id

    @property
    def merkle_root(self):
        return self._state_hash

    def initialize_futures(self, reads, others):
        """Set up every address with a _ContextFuture.

        Args:
            reads (list of str): addresses in the txn's input but not in
                prior state.
            others (list of str): addresses that don't have to
                wait for the background thread.
        Returns:
            None

        Raises:
            ValueError if reads and others are not disjoint.

        """
        if len(set(reads) & set(others)) > 0:
            raise ValueError("reads %, others %s must "
                             "be disjoint", reads, others)
        for add in reads:
            self._state[add] = _ContextFuture(address=add, wait_for_tree=True)
        for add in others:
            self._state[add] = _ContextFuture(address=add)

    def set_futures(self, address_value_dict, from_tree=False):
        """

        Args:
            address_value_dict (dict of str:bytes): The addresses and values
                to resolve the futures to.
            from_tree (bool): Whether the futures are being resolved

        Returns:

        """
        for add, val in address_value_dict.items():
            self._state.get(add).set_result(val, from_tree=from_tree)

    def get_writable_address_value_dict(self):
        add_value_dict = {}
        for add, val in self._state.items():
            if add in self._write_list:
                add_value_dict[add] = val
        return add_value_dict

    def get_state(self):
        """Return all of the state associated with the context.

        Returns:
            _state (dict of str: _ContextFuture): The context data

        """
        return self._state

    def get_from_prefetched(self, address_list):
        """Get address-ContextFuture tuples for addresses in the address_list.

        Args:
            address_list (list): a list of addresses

        Returns:
            found_values (list): a list of (address, ContextFuture) tuples

        Raises:
            AuthorizationException if an address is not within the inputs for
            the original transaction.

        """
        found_values = []
        for address in address_list:
            if address not in self._read_list:
                LOGGER.debug("Authorization exception, address: %s", address)
                raise AuthorizationException(address)
            found_values.append((address,
                                self._state.get(address)))
        return found_values

    def can_set(self, address_value_list):
        for add_value_dict in address_value_list:
            for address in add_value_dict.keys():
                if address not in self._write_list:
                    LOGGER.debug("Authorization exception, address: %s",
                                 address)
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
        self._contexts = _ThreadsafeContexts()

        self._address_queue = Queue()

        self._inflated_addresses = Queue()

        self._context_reader = _ContextReader(database, self._address_queue,
                                              self._inflated_addresses)
        self._context_reader.start()

        self._context_writer = _ContextWriter(self._inflated_addresses,
                                              self._contexts)
        self._context_writer.start()

    def get_first_root(self):
        if self._first_merkle_root is not None:
            return self._first_merkle_root
        self._first_merkle_root = MerkleDatabase(
            self._database).get_merkle_root()
        return self._first_merkle_root

    def create_context(self, state_hash, base_contexts, inputs, outputs):
        """Create a StateContext to run a transaction against.

        Args:
            state_hash: (str): Merkle root to base state on.
            base_contexts (list of str): Context ids of contexts that will
                have their state applied to make this context.
            inputs (list of str): Addresses that can be read from.
            outputs (list of str): Addresses that can be written to.
        Returns:
            context_id (str): the unique context_id of the session

        """

        context = StateContext(
            state_hash=state_hash,
            read_list=inputs,
            write_list=outputs,
            base_context_ids=base_contexts)

        self._contexts[context.session_id] = context
        contexts_asked_not_found = [cid for cid in base_contexts
                                    if cid not in self._contexts]
        if len(contexts_asked_not_found) > 0:
            raise KeyError(
                "Basing a new context off of context ids {} "
                "that are not in context manager".format(
                    contexts_asked_not_found))
        base_context_list = [self._contexts[cid] for cid in base_contexts]
        # Get the state from the base contexts
        prior_state = dict()
        for base_context in base_context_list:
            prior_state.update(base_context.get_state())

        addresses_already_in_state = set(prior_state.keys())
        reads = set(inputs) - addresses_already_in_state
        others = set(addresses_already_in_state | set(outputs)) - set(reads)
        context.initialize_futures(reads=list(reads),
                                   others=list(others))
        # Read the actual values that are based on _ContextFutures before
        # setting new futures with those values.
        prior_state_results = dict()
        for k, val_fut in prior_state.items():
            value = val_fut.result()
            prior_state_results[k] = value

        context.set_futures(prior_state_results)

        if len(reads) > 0:
            self._address_queue.put_nowait(
                (context.session_id, state_hash, list(reads)))
        return context.session_id

    def delete_context(self, context_id_list):
        """Delete contexts from the ContextManager.

        Args:
            context_id_list (list): a list of context ids

        Returns:
            None

        """
        for c_id in context_id_list:
            if c_id in self._contexts:
                del self._contexts[c_id]

    def get(self, context_id, address_list):
        """Get the values associated with list of addresses, for a specific
        context referenced by context_id.

        Args:
            context_id (str): the return value of create_context, referencing
                a particular context.
            address_list (list): a list of address strs

        Returns:
            values_list (list): a list of (address, value) tuples
        """

        if context_id not in self._contexts:
            return []
        context = self._contexts.get(context_id)
        return [(a, f.result())
                for a, f in context.get_from_prefetched(address_list)]

    def set(self, context_id, address_value_list):
        """Within a context, sets addresses to a value.

        Args:
            context_id (str): the context id returned by create_context
            address_value_list (list): list of {address: value} dicts

        Returns:
            (bool): True if the operation is successful, False if
                the context_id doesn't reference a known context.

        Raises:
            AuthorizationException if an address is specified to write to
                that was not in the original transaction's outputs.
        """

        if context_id not in self._contexts:
            LOGGER.warning("Context_id not in contexts, %s", context_id)
            return False

        context = self._contexts.get(context_id)
        # Where authorization on the address level happens.
        context.can_set(address_value_list)
        add_value_dict = {}
        for d in address_value_list:
            for add, val in d.items():
                add_value_dict[add] = val
        context.set_futures(add_value_dict)
        return True

    def get_squash_handler(self):
        def _squash(state_root, context_ids, persist):
            tree = MerkleDatabase(self._database, state_root)
            updates = dict()
            for c_id in context_ids:
                context = self._contexts[c_id]
                for add in context.get_state().keys():
                    if add in updates:
                        raise SquashException(
                            "Duplicate address {} in context {}".format(
                                add, c_id))

                effective_updates = {}
                for k, val_fut in context.get_state().items():
                    value = val_fut.result()
                    if value is not None:
                        effective_updates[k] = value

                updates.update(effective_updates)
            virtual = not persist
            state_hash = tree.update(updates, virtual=virtual)
            if persist:
                # clean up all contexts that are involved in being squashed.
                base_c_ids = []
                for c_id in context_ids:
                    base_c_ids += self._contexts[c_id].base_context_ids
                all_context_ids = base_c_ids + context_ids
                self.delete_context(all_context_ids)
            return state_hash
        return _squash

    def stop(self):
        self._address_queue.put_nowait(_SHUTDOWN_SENTINEL)
        self._inflated_addresses.put_nowait(_SHUTDOWN_SENTINEL)


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
            if context_state_addresslist_tuple is _SHUTDOWN_SENTINEL:
                break
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
    """Reads off of a shared queue from _ContextReader and writes values
    to the contexts shared with the ContextManager.

    """

    def __init__(self, inflated_addresses, contexts):
        """
        Args:
            inflated_addresses (queue.Queue): Contains the context id of the
                context to write to, and the address-value pairs.
            contexts (_ThreadsafeContexts): The datastructures to write the
                address-value pairs to.
        """
        super(_ContextWriter, self).__init__()
        self._inflated_addresses = inflated_addresses
        self._contexts = contexts

    def run(self):
        while True:
            context_id_list_tuple = self._inflated_addresses.get(
                block=True)
            if context_id_list_tuple is _SHUTDOWN_SENTINEL:
                break
            c_id, inflated_address_list = context_id_list_tuple
            inflated_value_map = {k: v for k, v in inflated_address_list}
            if c_id in self._contexts:
                self._contexts[c_id].set_futures(inflated_value_map,
                                                 from_tree=True)


class _ContextFuture(object):
    def __init__(self, address, wait_for_tree=False):
        self.address = address
        self._result = None
        self._result_is_set = False
        self._condition = Condition()
        self._wait_for_tree = wait_for_tree
        self._tree_has_set = False

    def done(self):
        return self._result_is_set

    def result(self):
        with self._condition:
            self._condition.wait_for(lambda: self._result_is_set)
            return self._result

    def set_result(self, result, from_tree=False):
        """Set the addresses's value. If the _ContextFuture needs to be
        resolved from a read from the MerkleTree first, wait to set the value
        until _tree_has_set is True.

        Args:
            result (bytes): The value at an address.
            from_tree (bool): Whether the value is coming from the MerkleTree,
                or if it is set from prior state.

        Returns:
            None
        """
        with self._condition:
            if self._wait_for_tree and not from_tree:
                self._condition.wait_for(lambda: self._tree_has_set)
            self._result = result
            self._result_is_set = True
            if self._wait_for_tree and from_tree:
                self._tree_has_set = True
            self._condition.notify_all()


class _ThreadsafeContexts(object):
    def __init__(self):
        self._lock = Lock()
        self._data = dict()

    def __getitem__(self, item):
        return self.get(item)

    def __setitem__(self, key, value):
        with self._lock:
            self._data[key] = value

    def __contains__(self, item):
        with self._lock:
            return item in self._data

    def get(self, item):
        with self._lock:
            return self._data[item]

    def __delitem__(self, key):
        with self._lock:
            del self._data[key]

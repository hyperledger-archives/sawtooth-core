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

import logging
import re
import uuid

from collections import deque
from threading import Condition
from threading import Lock
from threading import Thread
from queue import Queue

from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.protobuf.state_delta_pb2 import StateChange


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
    """A thread-safe data structure holding address-_ContextFuture pairs and
    the addresses that can be written to and read from.
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

        # Create copies of the read and write lists
        self._read_list = list(read_list)
        self._write_list = list(write_list)

        self._state = {}
        self._lock = Lock()

        self._read_only = False

        self.base_contexts = base_context_ids

        self._id = uuid.uuid4().hex

    @property
    def session_id(self):
        return self._id

    @property
    def merkle_root(self):
        return self._state_hash

    def _contains_and_set(self, address):
        return address in self._state and self._state[address].set_in_context()

    def _contains_and_not_set(self, add):
        return add in self._state and not self._state[add].set_in_context()

    def _contains(self, address):
        return address in self._state

    def __contains__(self, item):
        with self._lock:
            return self._contains(item)

    def _get(self, address):
        value = None
        if self._contains(address):
            value = self._state[address].result()
        return value

    def _get_if_set(self, address):
        value = None
        if self._contains_and_set(address):
            value = self._state[address].result()
        return value

    def _get_if_not_set(self, address):
        value = None
        if self._contains_and_not_set(address):
            value = self._state[address].result()
        return value

    def is_read_only(self):
        return self._read_only

    def make_read_only(self):
        with self._lock:
            if not self._read_only:
                for fut in self._state.values():
                    fut.make_read_only()
                self._read_only = True

    def get(self, addresses):
        """Returns the value in this context, or None, for each address in
        addresses. Useful for gets on the context manager.

        Args:
            addresses (list of str): The addresses to return values for, if
                within this context.

        Returns:
            results (list of bytes): The values in state for these addresses.
        """

        with self._lock:
            results = []
            for add in addresses:
                self._validate_read(add)
                results.append(self._get(add))
            return results

    def get_if_set(self, addresses):
        """Returns the value set in this context, or None, for each address in
        addresses.

        Args:
            addresses (list of str): The addresses to return values for, if set
                within this context.

        Returns:
            (list): bytes set at the address or None
        """

        with self._lock:
            results = []
            for add in addresses:
                results.append(self._get_if_set(add))
            return results

    def get_if_not_set(self, addresses):
        """Returns the value at an address if it was an input to the txn but
        never set. It returns None if that address was never set in the
        merkle database, or if the address is not within the context.

        Args:
            addresses (list of str): The full 70 character addresses.

        Returns:
            (list): bytes at that address but not set within the context
        """

        with self._lock:
            results = []
            for add in addresses:
                results.append(self._get_if_not_set(add))
            return results

    def get_all_if_set(self):
        """Return all the addresses and opaque values set in the context.
        Useful in the squash method.

        Returns:
            (dict of str to bytes): The addresses and bytes that have
                been set in the context.
        """

        with self._lock:
            results = {}
            for add, fut in self._state.items():
                if self._contains_and_set(add):
                    results[add] = fut.result()
            return results

    def create_prefetch(self, addresses):
        """Create futures needed before starting the process of reading the
        address's value from the merkle tree.

        Args:
            addresses (list of str): addresses in the txn's inputs that
                aren't in any base context (or any in the chain).
        """

        with self._lock:
            for add in addresses:
                self._state[add] = _ContextFuture(address=add,
                                                  wait_for_tree=True)

    def create_initial(self, address_values):
        """Create futures from inputs with the current value for that address
        at the start of that context.

        Args:
            address_values (list of tuple): The tuple is string, bytes of the
                address and value.
        """

        with self._lock:
            for add, val in address_values:
                self._state[add] = _ContextFuture(address=add, result=val)

    def set_from_tree(self, address_value_dict):
        """Set the result for each future at the given addresses with the value
        stored in the merkle database.

        Args:
            address_value_dict (dict of str: bytes): The unique
                full addresses that the bytes values should be set with.
        """

        for address, value in address_value_dict.items():
            if address in self._state:
                self._state[address].set_result(result=value,
                                                from_tree=True)

    def set_direct(self, address_value_dict):
        """Called in the context manager's set method to either overwrite the
        value for an address, or create a new future and immediately set a
        value in the future.

        Args:
            address_value_dict (dict of str:bytes): The unique full addresses
                with bytes to set at that address.

        Raises:
            AuthorizationException
        """

        with self._lock:
            for address, value in address_value_dict.items():
                self._validate_write(address)
                if address in self._state:
                    self._state[address].set_result(result=value)
                else:
                    fut = _ContextFuture(address=address)
                    self._state[address] = fut
                    fut.set_result(result=value)

    def _validate_write(self, address):
        """Raises an exception if the address is not allowed to be set
        in this context, based on txn outputs.

        Notes:
            Checks that the address is either listed fully as one of the
            outputs, or some portion of the address is listed as a namespace
            in the outputs of the txn.

        Args:
            address (str): The address to be validated. The context manager
                validates the address correctness (70 hex characters).
        Returns:
            None

        Raises:
            AuthorizationException
        """

        if not any(address.startswith(ns) for ns in self._write_list):
            raise AuthorizationException(address=address)

    def _validate_read(self, address):
        """Raises an exception if the address is not allowed to be read in
        this context, based on txn inputs.

        Args:
            address (str): An address to be validated.

        Returns:
            None

        Raises:
            AuthorizationException
        """

        if not any(address.startswith(ns) for ns in self._read_list):
            raise AuthorizationException(address=address)


class ContextManager(object):

    def __init__(self, database, state_delta_store):
        """

        Args:
            database (database.Database subclass): the subclass/implementation
                of the Database
            state_delta_store (StateDeltaStore): the store for state deltas
        """
        self._database = database
        self._state_delta_store = state_delta_store
        self._first_merkle_root = None
        self._contexts = _ThreadsafeContexts()

        self._address_regex = re.compile('^[0-9a-f]{70}$')

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

    def address_is_valid(self, address):

        return self._address_regex.match(address) is not None

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

        addresses_to_find = list(inputs)

        context = StateContext(
            state_hash=state_hash,
            read_list=inputs,
            write_list=outputs,
            base_context_ids=base_contexts)

        contexts_asked_not_found = [cid for cid in base_contexts
                                    if cid not in self._contexts]
        if len(contexts_asked_not_found) > 0:
            raise KeyError(
                "Basing a new context off of context ids {} "
                "that are not in context manager".format(
                    contexts_asked_not_found))

        contexts_in_chain = deque()
        contexts_in_chain.extend(base_contexts)
        reads = list(addresses_to_find)
        address_values = []
        context_ids_already_searched = []
        context_ids_already_searched.extend(base_contexts)

        # There are two loop exit conditions, either all the addresses that
        # are being searched for have been found, or we run out of contexts
        # in the chain of contexts.

        while len(reads) > 0:
            try:
                current_c_id = contexts_in_chain.popleft()
            except IndexError:
                # There aren't any more contexts known about.
                break
            current_context = self._contexts[current_c_id]
            if not current_context.is_read_only():
                current_context.make_read_only()

            # First, check for addresses that have been set in the context,
            # and remove those addresses from being asked about again. Here
            # any value of None means the address hasn't been set.

            values = current_context.get_if_set(reads)
            addresses_not_found = []
            for address, value in zip(reads, values):
                if value is not None:
                    address_values.append((address, value))
                else:
                    addresses_not_found.append(address)
            reads = addresses_not_found

            # Next check for addresses that might be in a context
            # because they were inputs.

            addresses_in_inputs = [address for address in reads
                                   if address in current_context]

            values = current_context.get_if_not_set(addresses_in_inputs)

            address_values.extend(list(zip(addresses_in_inputs, values)))

            for add in addresses_in_inputs:
                reads.remove(add)

            for c_id in current_context.base_contexts:
                if c_id not in context_ids_already_searched:
                    contexts_in_chain.append(c_id)
                    context_ids_already_searched.append(c_id)
        context.create_initial(address_values)

        self._contexts[context.session_id] = context

        if len(reads) > 0:
            context.create_prefetch(reads)
            self._address_queue.put_nowait(
                (context.session_id, state_hash, reads))
        return context.session_id

    def delete_contexts(self, context_id_list):
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

        Raises:
            AuthorizationException: Raised when an address in address_list is
                not authorized either by not being in the inputs for the
                txn associated with this context, or it is under a namespace
                but the characters that are under the namespace are not valid
                address characters.
        """

        if context_id not in self._contexts:
            return []
        for add in address_list:
            if not self.address_is_valid(address=add):
                raise AuthorizationException(address=add)

        context = self._contexts[context_id]
        values = context.get(list(address_list))
        values_list = list(zip(address_list, values))
        return values_list

    def set(self, context_id, address_value_list):
        """Within a context, sets addresses to a value.

        Args:
            context_id (str): the context id returned by create_context
            address_value_list (list): list of {address: value} dicts

        Returns:
            (bool): True if the operation is successful, False if
                the context_id doesn't reference a known context.

        Raises:
            AuthorizationException if an address is given in the
                address_value_list that was not in the original
                transaction's outputs, or was under a namespace but the
                characters after the namespace are not valid address
                characters.
        """

        if context_id not in self._contexts:
            LOGGER.warning("Context_id not in contexts, %s", context_id)
            return False

        context = self._contexts.get(context_id)

        add_value_dict = {}
        for d in address_value_list:
            for add, val in d.items():
                if not self.address_is_valid(address=add):
                    raise AuthorizationException(address=add)
                add_value_dict[add] = val
        context.set_direct(add_value_dict)
        return True

    def get_squash_handler(self):
        def _squash(state_root, context_ids, persist, clean_up):
            contexts_in_chain = deque()
            contexts_in_chain.extend(context_ids)
            context_ids_already_searched = []
            context_ids_already_searched.extend(context_ids)

            # There is only one exit condition and that is when all the
            # contexts have been accessed once.
            updates = dict()
            while len(contexts_in_chain) > 0:
                current_c_id = contexts_in_chain.popleft()
                current_context = self._contexts[current_c_id]
                if not current_context.is_read_only():
                    current_context.make_read_only()

                addresses_w_values = current_context.get_all_if_set()
                for add, val in addresses_w_values.items():
                    # Since we are moving backwards through the graph of
                    # contexts, only update if the address hasn't been set
                    if add not in updates:
                        updates[add] = val

                for c_id in current_context.base_contexts:
                    if c_id not in context_ids_already_searched:
                        contexts_in_chain.append(c_id)
                        context_ids_already_searched.append(c_id)

            if len(updates) == 0:
                return state_root

            tree = MerkleDatabase(self._database, state_root)
            virtual = not persist
            state_hash = tree.update(updates, virtual=virtual)
            if persist:
                # save the state changes to the state_delta_store
                changes = [StateChange(address=addr,
                                       value=value,
                                       type=StateChange.SET)
                           for addr, value in updates.items()]
                self._state_delta_store.save_state_deltas(state_hash, changes)
            if clean_up:
                self.delete_contexts(context_ids_already_searched)
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
        super(_ContextReader, self).__init__(name='_ContextReader')
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
        super(_ContextWriter, self).__init__(name='_ContextWriter')
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
                self._contexts[c_id].set_from_tree(inflated_value_map)


class _ContextFuture(object):
    """Controls access to bytes set in the _result variable. The booleans
     that are flipped in set_result, based on whether the value is being set
     from the merkle tree or a direct set on the context manager are needed
     to later determine whether the value was set in that context or was
     looked up as a new address location from the merkle tree and then only
     read from, not set.

    In any context the lifecycle of a _ContextFuture can be several paths:

    Input:
    Address not in base:
      F -----> get from merkle database ----> get from the context
    Address in base:
            |---> set (F)
      F --->|
            |---> get
    Output:
      Doesn't exist ----> set address in context (F)

    Input + Output:
    Address not in base:

                             |-> set
      F |-> get from merkle -|
        |                    |-> get
        |                    |
        |                    |-> noop
        |--> set Can happen before the pre-fetch operation


                     |-> set (F) ---> get
                     |
                     |-> set (F) ----> set
                     |
    Address in base: |-> set (F)
      Doesn't exist -|
                     |-> get Future doesn't exit in context
                     |
                     |-> get ----> set (F)

    """

    def __init__(self, address, result=None, wait_for_tree=False):
        self.address = address
        self._result = result
        self._result_set_in_context = False
        self._condition = Condition()
        self._wait_for_tree = wait_for_tree
        self._tree_has_set = False
        self._read_only = False

    def make_read_only(self):
        with self._condition:
            if self._wait_for_tree and not self._result_set_in_context:
                self._condition.wait_for(
                    lambda: self._tree_has_set or self._result_set_in_context)

            self._read_only = True

    def set_in_context(self):
        with self._condition:
            return self._result_set_in_context

    def result(self):
        """Return the value at an address, optionally waiting until it is
        set from the context_manager, or set based on the pre-fetch mechanism.

        Returns:
            (bytes): The opaque value for an address.
        """

        if self._read_only:
            return self._result
        with self._condition:
            if self._wait_for_tree and not self._result_set_in_context:
                self._condition.wait_for(
                    lambda: self._tree_has_set or self._result_set_in_context)
            return self._result

    def set_result(self, result, from_tree=False):
        """Set the addresses's value unless the future has been declared
        read only.

        Args:
            result (bytes): The value at an address.
            from_tree (bool): Whether the value is being set by a read from
                the merkle tree.

        Returns:
            None
        """

        if self._read_only:
            return

        with self._condition:
            if self._read_only:
                return
            if from_tree:
                # If the result has not been set in the context, overwrite the
                # value with the value from the merkle tree. Otherwise, do
                # nothing.
                if not self._result_set_in_context:
                    self._result = result
                    self._tree_has_set = True
            else:
                self._result = result
                self._result_set_in_context = True

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

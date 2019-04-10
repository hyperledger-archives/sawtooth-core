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

from collections import deque
from threading import Lock
from queue import Queue

from sawtooth_validator.concurrent.thread import InstrumentedThread
from sawtooth_validator.state.merkle import MerkleDatabase

from sawtooth_validator.execution.execution_context \
    import AuthorizationException
from sawtooth_validator.execution.execution_context import ExecutionContext


LOGGER = logging.getLogger(__name__)


class CreateContextException(Exception):
    pass


class SquashException(Exception):
    pass


_SHUTDOWN_SENTINEL = -1


class ContextManager:

    def __init__(self, database):
        """

        Args:
            database (database.Database subclass): the subclass/implementation
                of the Database
        """
        self._database = database
        self._first_merkle_root = None
        self._contexts = _ThreadsafeContexts()

        self._address_regex = re.compile('^[0-9a-f]{70}$')

        self._namespace_regex = re.compile('^([0-9a-f]{2}){0,35}$')

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

    def namespace_is_valid(self, namespace):

        return self._namespace_regex.match(namespace) is not None

    def create_context(self, state_hash, base_contexts, inputs, outputs):
        """Create a ExecutionContext to run a transaction against.

        Args:
            state_hash: (str): Merkle root to base state on.
            base_contexts (list of str): Context ids of contexts that will
                have their state applied to make this context.
            inputs (list of str): Addresses that can be read from.
            outputs (list of str): Addresses that can be written to.
        Returns:
            context_id (str): the unique context_id of the session
        """

        for address in inputs:
            if not self.namespace_is_valid(address):
                raise CreateContextException(
                    "Address or namespace {} listed in inputs is not "
                    "valid".format(address))
        for address in outputs:
            if not self.namespace_is_valid(address):
                raise CreateContextException(
                    "Address or namespace {} listed in outputs is not "
                    "valid".format(address))

        addresses_to_find = [add for add in inputs if len(add) == 70]

        address_values, reads = self._find_address_values_in_chain(
            base_contexts=base_contexts,
            addresses_to_find=addresses_to_find)

        context = ExecutionContext(
            state_hash=state_hash,
            read_list=inputs,
            write_list=outputs,
            base_context_ids=base_contexts)

        contexts_asked_not_found = [cid for cid in base_contexts
                                    if cid not in self._contexts]
        if contexts_asked_not_found:
            raise KeyError(
                "Basing a new context off of context ids {} "
                "that are not in context manager".format(
                    contexts_asked_not_found))

        context.create_initial(address_values)

        self._contexts[context.session_id] = context

        if reads:
            context.create_prefetch(reads)
            self._address_queue.put_nowait(
                (context.session_id, state_hash, reads))
        return context.session_id

    def _find_address_values_in_chain(self, base_contexts, addresses_to_find):
        """Breadth first search through the chain of contexts searching for
        the bytes values at the addresses in addresses_to_find.

        Args:
            base_contexts (list of str): The context ids to start with.
            addresses_to_find (list of str): Addresses to find values in the
                chain of contexts.

        Returns:
            tuple of found address_values and still not found addresses
        """

        contexts_in_chain = deque()
        contexts_in_chain.extend(base_contexts)
        reads = list(addresses_to_find)
        address_values = []
        context_ids_already_searched = []
        context_ids_already_searched.extend(base_contexts)

        # There are two loop exit conditions, either all the addresses that
        # are being searched for have been found, or we run out of contexts
        # in the chain of contexts.

        while reads:
            try:
                current_c_id = contexts_in_chain.popleft()
            except IndexError:
                # There aren't any more contexts known about.
                break
            current_context = self._contexts[current_c_id]

            # First, check for addresses that have been deleted.
            deleted_addresses = current_context.get_if_deleted(reads)
            for address in deleted_addresses:
                if address is not None:
                    address_values.append((address, None))

            reads = list(set(reads) - set(deleted_addresses))

            # Second, check for addresses that have been set in the context,
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

        return address_values, reads

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

    def delete(self, context_id, address_list):
        """Delete the values associated with list of addresses, for a specific
        context referenced by context_id.

        Args:
            context_id (str): the return value of create_context, referencing
                a particular context.
            address_list (list): a list of address strs

        Returns:
            (bool): True if the operation is successful, False if
                the context_id doesn't reference a known context.

        Raises:
            AuthorizationException: Raised when an address in address_list is
                not authorized either by not being in the inputs for the
                txn associated with this context, or it is under a namespace
                but the characters that are under the namespace are not valid
                address characters.
        """

        if context_id not in self._contexts:
            return False

        context = self._contexts[context_id]

        for add in address_list:
            if not self.address_is_valid(address=add):
                raise AuthorizationException(address=add)

        context.delete_direct(address_list)

        return True

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

        addresses_in_ctx = [add for add in address_list if add in context]
        addresses_not_in_ctx = list(set(address_list) - set(addresses_in_ctx))

        values = context.get(addresses_in_ctx)
        values_list = list(zip(addresses_in_ctx, values))
        if addresses_not_in_ctx:
            # Validate the addresses that won't be validated by a direct get on
            # the context.
            for address in addresses_not_in_ctx:
                context.validate_read(address)
            try:
                address_values, reads = self._find_address_values_in_chain(
                    base_contexts=[context_id],
                    addresses_to_find=addresses_not_in_ctx)
            except KeyError:
                # This is in the exceptional case when a txn is in flight
                # and so the context may not exist but the tp is asking
                # about it.
                return []

            values_list.extend(address_values)

            if reads:
                tree = MerkleDatabase(self._database, context.merkle_root)
                add_values = []
                for add in reads:
                    value = None
                    try:
                        value = tree.get(add)
                    except KeyError:
                        # The address is not in the radix tree/merkle tree
                        pass
                    add_values.append((add, value))
                values_list.extend(add_values)

            values_list.sort(key=lambda x: address_list.index(x[0]))

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
            deletes = set()
            while contexts_in_chain:
                current_c_id = contexts_in_chain.popleft()
                current_context = self._contexts[current_c_id]
                if not current_context.is_read_only():
                    current_context.make_read_only()

                addresses_w_values = current_context.get_all_if_set()
                for add, val in addresses_w_values.items():
                    # Since we are moving backwards through the graph of
                    # contexts, only update if the address hasn't been set
                    # or deleted
                    if add not in updates and add not in deletes:
                        updates[add] = val

                addresses_w_values = current_context.get_all_if_deleted()
                for add, _ in addresses_w_values.items():
                    # Since we are moving backwards through the graph of
                    # contexts, only add to deletes if the address hasn't been
                    # previously deleted or set in the graph
                    if add not in updates and add not in deletes:
                        deletes.add(add)

                for c_id in current_context.base_contexts:
                    if c_id not in context_ids_already_searched:
                        contexts_in_chain.append(c_id)
                        context_ids_already_searched.append(c_id)

            tree = MerkleDatabase(self._database, state_root)

            # filter the delete list to just those items in the tree
            deletes = [addr for addr in deletes if addr in tree]

            if not updates and not deletes:
                state_hash = state_root
            else:
                virtual = not persist
                state_hash = tree.update(updates, deletes, virtual=virtual)

            if clean_up:
                self.delete_contexts(context_ids_already_searched)
            return state_hash
        return _squash

    def stop(self):
        self._address_queue.put_nowait(_SHUTDOWN_SENTINEL)
        self._inflated_addresses.put_nowait(_SHUTDOWN_SENTINEL)

    def add_execution_data(self, context_id, data):
        """Within a context, append data to the execution result.

        Args:
            context_id (str): the context id returned by create_context
            data (bytes): data to append

        Returns:
            (bool): True if the operation is successful, False if
                the context_id doesn't reference a known context.
        """
        if context_id not in self._contexts:
            LOGGER.warning("Context_id not in contexts, %s", context_id)
            return False

        context = self._contexts.get(context_id)
        context.add_execution_data(data)
        return True

    def add_execution_event(self, context_id, event):
        """Within a context, append data to the execution result.

        Args:
            context_id (str): the context id returned by create_context
            data_type (str): type of data to append
            data (bytes): data to append

        Returns:
            (bool): True if the operation is successful, False if
                the context_id doesn't reference a known context.
        """
        if context_id not in self._contexts:
            LOGGER.warning("Context_id not in contexts, %s", context_id)
            return False

        context = self._contexts.get(context_id)
        context.add_execution_event(event)
        return True

    def get_execution_results(self, context_id):
        context = self._contexts.get(context_id)
        return (context.get_all_if_set().copy(),
                context.get_all_if_deleted().copy(),
                context.get_execution_events().copy(),
                context.get_execution_data().copy())


class _ContextReader(InstrumentedThread):
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


class _ContextWriter(InstrumentedThread):
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


class _ThreadsafeContexts:
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

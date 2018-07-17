# Copyright 2017 Intel Corporation
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
import uuid
from threading import Condition
from threading import Lock


LOGGER = logging.getLogger(__name__)


class AuthorizationException(Exception):
    def __init__(self, address):
        super(AuthorizationException, self).__init__(
            "Not authorized to read/write to {}".format(address))


class ExecutionContext:
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
        self._read_list = read_list.copy()
        self._write_list = write_list.copy()

        self._state = {}
        self._lock = Lock()

        self._read_only = False

        self.base_contexts = base_context_ids

        self._id = uuid.uuid4().hex

        self._execution_data = []
        self._execution_events = []

    @property
    def session_id(self):
        return self._id

    @property
    def merkle_root(self):
        return self._state_hash

    def _contains_and_deleted(self, address):
        return address in self._state and \
            self._state[address].deleted_in_context()

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

    def _get_if_deleted(self, address):
        add = None
        if self._contains_and_deleted(address=address):
            add = address
        return add

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
                self.validate_read(add)
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

    def get_if_deleted(self, addresses):
        """Returns a list of addresses that have been deleted, or None if it
        hasn't been deleted.

        Args:
            addresses (list of str): The addresses to check if deleted.

        Returns:
            (list of str): The addresses, if deleted, or None.
        """

        with self._lock:
            results = []
            for add in addresses:
                results.append(self._get_if_deleted(add))
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

    def get_all_if_deleted(self):
        """Return all the addresses deleted in the context.
        Useful in the squash method.

        Returns:
            (dict of str to bytes): The addresses and bytes that have
                been deleted in the context.
        """

        with self._lock:
            results = {}
            for add, fut in self._state.items():
                if self._contains_and_deleted(add):
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

    def delete_direct(self, addresses):
        """Called in the context manager's delete method to either
        mark an entry for deletion , or create a new future and immediately
        set it for deletion in the future.

        Args:
            address_list (list of str): The unique full addresses.

        Raises:
            AuthorizationException
        """

        with self._lock:
            for address in addresses:
                self._validate_write(address)
                if address in self._state:
                    self._state[address].set_deleted()
                else:
                    fut = _ContextFuture(address=address)
                    self._state[address] = fut
                    fut.set_deleted()

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

    def validate_read(self, address):
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

    def add_execution_data(self, data):
        with self._lock:
            self._execution_data.append(data)

    def get_execution_data(self):
        with self._lock:
            return self._execution_data.copy()

    def add_execution_event(self, event):
        with self._lock:
            self._execution_events.append(event)

    def get_execution_events(self):
        with self._lock:
            return self._execution_events.copy()


class _ContextFuture:
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
        self._deleted = False

    def make_read_only(self):
        with self._condition:
            if self._wait_for_tree and not self._result_set_in_context:
                self._condition.wait_for(
                    lambda: self._tree_has_set or self._result_set_in_context)

            self._read_only = True

    def set_in_context(self):
        with self._condition:
            return self._result_set_in_context

    def deleted_in_context(self):
        with self._condition:
            return self._deleted

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

    def set_deleted(self):
        self._result_set_in_context = False
        self._deleted = True

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
            if not from_tree:
                LOGGER.warning("Tried to set address %s on a"
                               " read-only context.",
                               self.address)
            return

        with self._condition:
            if self._read_only:
                if not from_tree:
                    LOGGER.warning("Tried to set address %s on a"
                                   " read-only context.",
                                   self.address)
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
                self._deleted = False

            self._condition.notify_all()

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

import abc
import logging
from time import time
from functools import cmp_to_key
from threading import Condition
# pylint: disable=import-error,no-name-in-module
# needed for google.protobuf import
from google.protobuf.message import DecodeError

from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.state.batch_tracker import BatchFinishObserver
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus

from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf import validator_pb2


LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 300
MAX_PAGE_SIZE = 1000


class _ResponseFailed(BaseException):
    """Raised when a response failed to complete and should be sent as is.

    Args:
        status (enum): Status to be sent with the incomplete response

    Attributes:
        status (enum): Status to be sent with the incomplete response
    """
    def __init__(self, status):
        super().__init__()
        self.status = status


class _ClientRequestHandler(Handler, metaclass=abc.ABCMeta):
    """Parent class for all Client Request Handlers.

    Handles the repetitive tasks of parsing a client request, and formatting
    the response. Also includes some helper methods common to multiple client
    handlers. Child classes should not implement the `handle` method directly,
    instead defining a unique `_respond` method specified below.

    Args:
        request_proto (class): Protobuf class of the request to be handled
        response_proto (class): Protobuf class of the response to be sent
        response_type (enum): Message status of the response
        tree (MerkleDatabase, optional): State tree to be queried
        block_store (BlockStoreAdapter, optional): Block chain to be queried
        batch_cache (TimedCache, optional): A cache of Batches being processed

    Attributes:
        _status (class): Convenience ref to response_proto for accessing enums
    """

    def __init__(self, request_proto, response_proto, response_type,
                 tree=None, block_store=None, batch_cache=None):
        self._request_proto = request_proto
        self._response_proto = response_proto
        self._response_type = response_type
        self._status = response_proto

        self._tree = tree
        self._block_store = block_store
        self._batch_cache = batch_cache

    def handle(self, connection_id, message_content):
        """Handles parsing incoming requests, and wrapping the final response.

        Args:
            connection_id (str): ZMQ identity sent over ZMQ socket
            message_content (bytes): Byte encoded request protobuf to be parsed

        Returns:
            HandlerResult: result to be sent in response back to client
        """
        try:
            request = self._request_proto()
            request.ParseFromString(message_content)
        except DecodeError:
            LOGGER.info('Protobuf %s failed to deserialize', request)
            return self._wrap_result(self._status.INTERNAL_ERROR)

        try:
            response = self._respond(request)
        except _ResponseFailed as e:
            response = e.status

        return self._wrap_result(response)

    @abc.abstractmethod
    def _respond(self, request):
        """This method must be implemented by each child to build its response.

        Args:
            request (object): A parsed request object of the specified protobuf

        Returns:
            enum: An enum status, or...
            dict: A dict of attributes for the response protobuf
        """
        raise NotImplementedError('Client Handler must have _respond method')

    def _wrap_result(self, response):
        """Wraps child's response in a HandlerResult to be sent back to client.

        Args:
            response (enum or dict): Either an integer status enum, or a dict
                of attributes to be added to the protobuf response.
        """
        if isinstance(response, int):
            response = self._wrap_response(response)

        return HandlerResult(
            status=HandlerStatus.RETURN,
            message_out=self._response_proto(**response),
            message_type=self._response_type)

    def _wrap_response(self, status=None, **kwargs):
        """Convenience method to wrap a status with any key word args.

        Args:
            status (enum): enum response status, defaults to OK

        Returns:
            dict: inlcudes a 'status' attribute and any key word arguments
        """
        kwargs['status'] = status if status is not None else self._status.OK
        return kwargs

    def _get_head_block(self, request):
        """Fetches the request specified head block, or the chain head.

        Note:
            This method will fail if `_block_store` has not been set

        Args:
            request (object): The parsed protobuf request object

        Returns:
            Block: the block object at the head of the requested chain

        Raises:
            ResponseFailed: Failed to retrieve a head block
        """
        if request.head_id:
            try:
                return self._block_store[request.head_id].block
            except KeyError as e:
                LOGGER.debug('Unable to find block "%s" in store', e)
                raise _ResponseFailed(self._status.NO_ROOT)

        elif self._block_store.chain_head:
            return self._block_store.chain_head.block

        else:
            LOGGER.debug('Unable to get chain head from block store')
            raise _ResponseFailed(self._status.NOT_READY)

    def _set_root(self, request):
        """Sets the root of the merkle tree, returning any head id used.

        Note:
            This method will fail if `_tree` has not been set

        Args:
            request (object): The parsed protobuf request object

        Returns:
            None: if a merkle_root is specified directly, no id is returned
            str: the id of the head block used to specify the root

        Raises:
            ResponseFailed: Failed to set the root if the merkle tree
        """
        if request.merkle_root:
            root = request.merkle_root
            head_id = None
        else:
            head = self._get_head_block(request)
            header = BlockHeader()
            header.ParseFromString(head.header)
            root = header.state_root_hash
            head_id = head.header_signature

        try:
            self._tree.set_merkle_root(root)
        except KeyError as e:
            LOGGER.debug('Unable to find root "%s" in database', e)
            raise _ResponseFailed(self._status.NO_ROOT)

        return head_id

    def _list_store_resources(self, request, head_id, filter_ids,
                              resource_fetcher, block_xform):
        """Builds a list of blocks or resources derived from blocks,
        handling multiple possible filter requests:
            - filtered by a set of ids
            - filtered by head block
            - filtered by both id and head block
            - not filtered (all current resources)

        Note:
            This method will fail if `_block_store` has not been set

        Args:
            request (object): The parsed protobuf request object
            head_id (str): Either request.head_id, or the current chain head
            filter_ids (list of str): the resource ids (if any) to filter by
            resource_fetcher (function): Fetches a resource by its id
                Expected args:
                    resource_id: The id of the resource to be fetched
                Expected return:
                    object: The resource to be appended to the results
            block_xform (function): Transforms a block into a list of resources
                Expected args:
                    block: A block object from the block store
                Expected return:
                    list: To be concatenated to the end of the results

        Returns:
            list: List of blocks or data from blocks. If filtered by ids,
                they will be listed in the same order as the id filters,
                otherwise they will be ordered from newest to oldest
        """
        resources = []

        # Simply fetch by id if filtered by id but not by head block
        if filter_ids and not request.head_id:
            for resource_id in filter_ids:
                try:
                    resources.append(resource_fetcher(resource_id))
                except (KeyError, ValueError, TypeError):
                    # Invalid ids should be omitted, not raise an exception
                    pass

        # Traverse block chain to build results for most scenarios
        else:
            current_id = head_id
            while current_id in self._block_store:
                block = self._block_store[current_id].block
                resources += block_xform(block)
                header = BlockHeader()
                header.ParseFromString(block.header)
                current_id = header.previous_block_id

        # If filtering by head AND ids, the traverse results must be winnowed
        if request.head_id and filter_ids:
            matches = {
                r.header_signature: r for r in resources
                if r.header_signature in filter_ids}
            resources = [matches[i] for i in filter_ids if i in matches]

        return resources


class _Pager(object):
    """A static class containing methods to paginate lists of resources.

    Contains a paginate method, as well as two helpers to fetch index of a
    resource by its id (either address or header_signature), or conversely
    to fetch the id by an index.
    """
    @classmethod
    def paginate_resources(cls, request, resources, on_fail_status):
        """Truncates a list of resources based on PagingControls

        Args:
            request (object): The parsed protobuf request object
            resources (list of objects): The resources to be paginated

        Returns:
            list: The paginated list of resources
            object: The PagingResponse to be sent back to the client
        """
        if not resources:
            return resources, client_pb2.PagingResponse(total_resources=0)

        paging = request.paging
        count = min(paging.count, MAX_PAGE_SIZE) or MAX_PAGE_SIZE

        # Find the start index from the location marker sent
        try:
            if paging.start_id:
                start_index = cls.index_by_id(paging.start_id, resources)
            elif paging.end_id:
                end_index = cls.index_by_id(paging.end_id, resources)
                start_index = end_index + 1 - count
            else:
                start_index = paging.start_index

            if start_index < 0 or start_index >= len(resources):
                raise AssertionError
        except AssertionError:
            raise _ResponseFailed(on_fail_status)

        paged_resources = resources[start_index: start_index + count]

        paging_response = client_pb2.PagingResponse(
            next_id=cls.id_by_index(start_index + count, resources),
            previous_id=cls.id_by_index(start_index - 1, resources),
            start_index=start_index,
            total_resources=len(resources))

        return paged_resources, paging_response

    @classmethod
    def index_by_id(cls, target_id, resources):
        """Helper method to fetch the index of a resource by its id or address

        Args:
            resources (list of objects): The resources to be paginated
            target_id (string): The address or header_signature of the resource

        Returns:
            integer: The index of the target resource

        Raises:
            AssertionError: Raised if the target is not found
        """
        for index in range(len(resources)):
            if cls.id_by_index(index, resources) == target_id:
                return index

        raise AssertionError

    @staticmethod
    def id_by_index(index, resources):
        """Helper method to fetch the id or address of a resource by its index

        Args:
            resources (list of objects): The resources to be paginated
            index (integer): The index of the target resource

        Returns:
            str: The address or header_signature of the resource,
                returns an empty string if not found
        """
        if index < 0 or index >= len(resources):
            return ''

        try:
            return resources[index].header_signature
        except AttributeError:
            return resources[index].address


class _Sorter(object):
    """A static class containing a method to sort lists of resources based on
    SortControls sent with the request.
    """
    @classmethod
    def sort_resources(cls, request, resources, fail_enum, header_proto=None):
        """Sorts a list of resources based on a list of sort controls

        Args:
            request (object): The parsed protobuf request object
            resources (list of objects): The resources to be sorted
            fail_enum (int, enum): The enum status to raise with invalid keys
            header_proto(class): Class to decode a resources header

        Returns:
            list: The sorted list of resources
        """
        if not request.sorting:
            return resources

        value_handlers = cls._get_handler_set(request, fail_enum, header_proto)

        def sorter(resource_a, resource_b):
            for handler in value_handlers:
                val_a, val_b = handler.get_sort_values(resource_a, resource_b)

                if val_a < val_b:
                    return handler.xform_result(-1)
                if val_a > val_b:
                    return handler.xform_result(1)

            return 0

        return sorted(resources, key=cmp_to_key(sorter))

    @classmethod
    def _get_handler_set(cls, request, fail_enum, header_proto=None):
        """Goes through the list of SortControls and returns a list of
        unique _ValueHandlers. Maintains order, but drops SortControls that
        have already appeared to help prevent spamming.
        """
        added = set()
        handlers = []

        for controls in request.sorting:
            control_bytes = controls.SerializeToString()
            if control_bytes not in added:
                added.add(control_bytes)
                handlers.append(
                    cls._ValueHandler(controls, fail_enum, header_proto))

        return handlers

    class _ValueHandler(object):
        """Handles fetching proper compare values for one SortControls.

        Args:
            controls (object): Individual SortControl object
            fail_status (integer, enum): Status to send when controls are bad
            header_proto (class): Class to decode the resource header
        """
        def __init__(self, controls, fail_status, header_proto=None):
            self._keys = controls.keys
            self._compare_length = controls.compare_length
            self._fail_status = fail_status
            self._header_proto = header_proto

            if controls.reverse:
                self.xform_result = lambda x: -x
            else:
                self.xform_result = lambda x: x

            if header_proto and self._keys[0] == 'header':
                self._had_explicit_header = True
                self._keys = self._keys[1:]
            else:
                self._had_explicit_header = False

        def get_sort_values(self, resource_a, resource_b):
            """Applies sort control logic to fetch from two resources the
            values that should actually be compared.
            """
            if (self._had_explicit_header or
                    self._header_proto and
                    not hasattr(resource_a, self._keys[0])):
                resource_a = self._get_header(resource_a)
                resource_b = self._get_header(resource_b)

            for key in self._keys:
                try:
                    resource_a = getattr(resource_a, key)
                    resource_b = getattr(resource_b, key)
                except AttributeError:
                    raise _ResponseFailed(self._fail_status)

            if self._compare_length:
                try:
                    resource_a = len(resource_a)
                    resource_b = len(resource_b)
                except TypeError:
                    raise _ResponseFailed(self._fail_status)

            return resource_a, resource_b

        def _get_header(self, resource):
            """Fetches a header from a resource.
            """
            header = self._header_proto()
            header.ParseFromString(resource.header)
            return header


class _BatchWaiter(BatchFinishObserver):
    """An observer which provides a method which locks until every batch in a
    set of ids is committed.

    Args:
        batch_tracker (BatchTracker): The BatchTracker that will notify the
            BatchWaiter that all of the batches it is interested in are no
            longer PENDING.
    """
    def __init__(self, batch_tracker):
        self._batch_tracker = batch_tracker
        self._wait_condition = Condition()
        self._statuses = None

    def notify_batches_finished(self, statuses):
        """Called by the BatchTracker the _BatchWaiter is observing. Should not
        be called by handlers.

        Args:
            statuses (dict of int): A dict with keys of batch ids, and values
                of status enums
        """
        with self._wait_condition:
            self._statuses = statuses
            self._wait_condition.notify()

    def wait_for_batches(self, batch_ids, timeout=None):
        """Locks until a list of batch ids is committed to the block chain
        or a timeout is exceeded. Returns the statuses of those batches.

        Args:
            batch_ids (list of str): The ids of the batches to wait for
            timeout(int): Maximum time in seconds to wait for

        Returns:
            list of BatchStatus: BatchStatuses to send back to client
        """
        self._batch_tracker.watch_statuses(self, batch_ids)
        timeout = timeout or DEFAULT_TIMEOUT
        start_time = time()

        with self._wait_condition:
            while True:
                if self._statuses or time() - start_time > timeout:
                    return [client_pb2.BatchStatus(batch_id=i,
                                                   status=self._statuses[i])
                            for i in batch_ids]
                self._wait_condition.wait(timeout - (time() - start_time))


class BatchSubmitFinisher(_ClientRequestHandler):
    def __init__(self, batch_tracker):
        self._batch_tracker = batch_tracker
        super().__init__(
            client_pb2.ClientBatchSubmitRequest,
            client_pb2.ClientBatchSubmitResponse,
            validator_pb2.Message.CLIENT_BATCH_SUBMIT_RESPONSE)

    def _respond(self, request):
        if not request.wait_for_commit:
            return self._status.OK

        waiter = _BatchWaiter(self._batch_tracker)
        batch_ids = [b.header_signature for b in request.batches]
        statuses = waiter.wait_for_batches(batch_ids, request.timeout)

        return self._wrap_response(batch_statuses=statuses)


class BatchStatusRequest(_ClientRequestHandler):
    def __init__(self, batch_tracker):
        self._batch_tracker = batch_tracker
        super().__init__(
            client_pb2.ClientBatchStatusRequest,
            client_pb2.ClientBatchStatusResponse,
            validator_pb2.Message.CLIENT_BATCH_STATUS_RESPONSE)

    def _respond(self, request):
        if request.wait_for_commit:
            waiter = _BatchWaiter(self._batch_tracker)
            statuses = waiter.wait_for_batches(
                request.batch_ids,
                request.timeout)
        else:
            statuses_dict = self._batch_tracker.get_statuses(request.batch_ids)
            statuses = [client_pb2.BatchStatus(batch_id=i,
                                               status=statuses_dict[i])
                        for i in request.batch_ids]

        if not statuses:
            return self._status.NO_RESOURCE

        return self._wrap_response(batch_statuses=statuses)


class StateCurrentRequest(_ClientRequestHandler):
    def __init__(self, current_root_func):
        self._get_root = current_root_func
        super().__init__(
            client_pb2.ClientStateCurrentRequest,
            client_pb2.ClientStateCurrentResponse,
            validator_pb2.Message.CLIENT_STATE_CURRENT_RESPONSE)

    def _respond(self, request):
        return self._wrap_response(merkle_root=self._get_root())


class StateListRequest(_ClientRequestHandler):
    def __init__(self, database, block_store):
        super().__init__(
            client_pb2.ClientStateListRequest,
            client_pb2.ClientStateListResponse,
            validator_pb2.Message.CLIENT_STATE_LIST_RESPONSE,
            tree=MerkleDatabase(database),
            block_store=block_store)

    def _respond(self, request):
        head_id = self._set_root(request)

        # Fetch leaves and encode as protobuf
        leaves = [
            client_pb2.Leaf(address=a, data=v) for a, v in
            self._tree.leaves(request.address or '').items()]

        # Order leaves, remove if tree.leaves refactored to be ordered
        leaves.sort(key=lambda l: l.address)

        leaves = _Sorter.sort_resources(
            request,
            leaves,
            self._status.INVALID_SORT)

        leaves, paging = _Pager.paginate_resources(
            request,
            leaves,
            self._status.INVALID_PAGING)

        if not leaves:
            return self._wrap_response(
                self._status.NO_RESOURCE,
                head_id=head_id,
                paging=paging)

        return self._wrap_response(
            head_id=head_id,
            paging=paging,
            leaves=leaves)


class StateGetRequest(_ClientRequestHandler):
    def __init__(self, database, block_store):
        super().__init__(
            client_pb2.ClientStateGetRequest,
            client_pb2.ClientStateGetResponse,
            validator_pb2.Message.CLIENT_STATE_GET_RESPONSE,
            tree=MerkleDatabase(database),
            block_store=block_store)

    def _respond(self, request):
        head_id = self._set_root(request)

        # Fetch leaf value
        try:
            value = self._tree.get(request.address)
        except KeyError:
            LOGGER.debug('Unable to find entry at address %s', request.address)
            return self._status.NO_RESOURCE
        except ValueError:
            LOGGER.debug('Address %s is a nonleaf', request.address)
            return self._status.INVALID_ADDRESS

        return self._wrap_response(head_id=head_id, value=value)


class BlockListRequest(_ClientRequestHandler):
    def __init__(self, block_store):
        super().__init__(
            client_pb2.ClientBlockListRequest,
            client_pb2.ClientBlockListResponse,
            validator_pb2.Message.CLIENT_BLOCK_LIST_RESPONSE,
            block_store=block_store)

    def _respond(self, request):
        head_id = self._get_head_block(request).header_signature
        blocks = self._list_store_resources(
            request,
            head_id,
            request.block_ids,
            lambda filter_id: self._block_store[filter_id].block,
            lambda block: [block])

        blocks = _Sorter.sort_resources(
            request,
            blocks,
            self._status.INVALID_SORT,
            BlockHeader)

        blocks, paging = _Pager.paginate_resources(
            request,
            blocks,
            self._status.INVALID_PAGING)

        if not blocks:
            return self._wrap_response(
                self._status.NO_RESOURCE,
                head_id=head_id,
                paging=paging)

        return self._wrap_response(
            head_id=head_id,
            paging=paging,
            blocks=blocks)


class BlockGetRequest(_ClientRequestHandler):
    def __init__(self, block_store):
        super().__init__(
            client_pb2.ClientBlockGetRequest,
            client_pb2.ClientBlockGetResponse,
            validator_pb2.Message.CLIENT_BLOCK_GET_RESPONSE,
            block_store=block_store)

    def _respond(self, request):
        try:
            block = self._block_store[request.block_id].block
        except KeyError as e:
            LOGGER.debug(e)
            return self._status.NO_RESOURCE
        return self._wrap_response(block=block)


class BatchListRequest(_ClientRequestHandler):
    def __init__(self, block_store):
        super().__init__(
            client_pb2.ClientBatchListRequest,
            client_pb2.ClientBatchListResponse,
            validator_pb2.Message.CLIENT_BATCH_LIST_RESPONSE,
            block_store=block_store)

    def _respond(self, request):
        head_id = self._get_head_block(request).header_signature
        batches = self._list_store_resources(
            request,
            head_id,
            request.batch_ids,
            self._block_store.get_batch,
            lambda block: [a for a in block.batches])

        batches = _Sorter.sort_resources(
            request,
            batches,
            self._status.INVALID_SORT,
            BatchHeader)

        batches, paging = _Pager.paginate_resources(
            request,
            batches,
            self._status.INVALID_PAGING)

        if not batches:
            return self._wrap_response(
                self._status.NO_RESOURCE,
                head_id=head_id,
                paging=paging)

        return self._wrap_response(
            head_id=head_id,
            paging=paging,
            batches=batches)


class BatchGetRequest(_ClientRequestHandler):
    def __init__(self, block_store):
        super().__init__(
            client_pb2.ClientBatchGetRequest,
            client_pb2.ClientBatchGetResponse,
            validator_pb2.Message.CLIENT_BATCH_GET_RESPONSE,
            block_store=block_store)

    def _respond(self, request):
        try:
            batch = self._block_store.get_batch(request.batch_id)
        except ValueError as e:
            LOGGER.debug(e)
            return self._status.NO_RESOURCE
        return self._wrap_response(batch=batch)


class TransactionListRequest(_ClientRequestHandler):
    def __init__(self, block_store):
        super().__init__(
            client_pb2.ClientTransactionListRequest,
            client_pb2.ClientTransactionListResponse,
            validator_pb2.Message.CLIENT_TRANSACTION_LIST_RESPONSE,
            block_store=block_store)

    def _respond(self, request):
        head_id = self._get_head_block(request).header_signature
        transactions = self._list_store_resources(
            request,
            head_id,
            request.transaction_ids,
            self._block_store.get_transaction,
            lambda block: [t for a in block.batches for t in a.transactions])

        transactions = _Sorter.sort_resources(
            request,
            transactions,
            self._status.INVALID_SORT,
            TransactionHeader)

        transactions, paging = _Pager.paginate_resources(
            request,
            transactions,
            self._status.INVALID_PAGING)

        if not transactions:
            return self._wrap_response(
                self._status.NO_RESOURCE,
                head_id=head_id,
                paging=paging)

        return self._wrap_response(
            head_id=head_id,
            paging=paging,
            transactions=transactions)


class TransactionGetRequest(_ClientRequestHandler):
    def __init__(self, block_store):
        super().__init__(
            client_pb2.ClientTransactionGetRequest,
            client_pb2.ClientTransactionGetResponse,
            validator_pb2.Message.CLIENT_TRANSACTION_GET_RESPONSE,
            block_store=block_store)

    def _respond(self, request):
        try:
            txn = self._block_store.get_transaction(request.transaction_id)
        except ValueError as e:
            LOGGER.debug(e)
            return self._status.NO_RESOURCE
        return self._wrap_response(transaction=txn)

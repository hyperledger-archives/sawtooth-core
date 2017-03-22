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
# pylint: disable=import-error,no-name-in-module
# needed for google.protobuf import
from google.protobuf.message import DecodeError

from sawtooth_validator.state.merkle import MerkleDatabase
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus

from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.protobuf import validator_pb2


LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 300


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

    def handle(self, identity, message_content):
        """Handles parsing incoming requests, and wrapping the final response.

        Args:
            identity (str): ZMQ identity sent over ZMQ socket
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
        except self._ResponseFailed as e:
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
            _ResponseFailed: Failed to retrieve a head block
        """
        if request.head_id:
            try:
                return self._block_store[request.head_id].block
            except KeyError as e:
                LOGGER.debug('Unable to find block "%s" in store', e)
                raise self._ResponseFailed(self._status.NO_ROOT)

        elif self._block_store.chain_head:
            return self._block_store.chain_head.block

        else:
            LOGGER.debug('Unable to get chain head from block store')
            raise self._ResponseFailed(self._status.NOT_READY)

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
            _ResponseFailed: Failed to set the root if the merkle tree
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
            raise self._ResponseFailed(self._status.NO_ROOT)

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

    def _get_statuses(self, batch_ids):
        """Fetches the committed statuses for a set of batch ids.

        Note:
            This method will fail without a `_block_store` and `_batch_cache`

        Args:
            batch_ids (list of str): The set of batch ids to be queried

        Returns:
            dict of enum: keys are batch ids, and values are their status enum
        """
        statuses = {}
        for batch_id in batch_ids:
            if self._block_store.has_batch(batch_id):
                statuses[batch_id] = self._status.COMMITTED
            elif batch_id in self._batch_cache:
                statuses[batch_id] = self._status.PENDING
            else:
                statuses[batch_id] = self._status.UNKNOWN
        return statuses


class BatchSubmitFinisher(_ClientRequestHandler):
    def __init__(self, block_store, batch_cache):
        super().__init__(
            client_pb2.ClientBatchSubmitRequest,
            client_pb2.ClientBatchSubmitResponse,
            validator_pb2.Message.CLIENT_BATCH_SUBMIT_RESPONSE,
            block_store=block_store,
            batch_cache=batch_cache)

    def _respond(self, request):
        if not request.wait_for_commit:
            return self._status.OK

        batch_ids = [b.header_signature for b in request.batches]

        self._block_store.wait_for_batch_commits(
            batch_ids=batch_ids,
            timeout=request.timeout or DEFAULT_TIMEOUT)

        statuses = self._get_statuses(batch_ids)
        return self._wrap_response(batch_statuses=statuses)


class BatchStatusRequest(_ClientRequestHandler):
    def __init__(self, block_store, batch_cache):
        super().__init__(
            client_pb2.ClientBatchStatusRequest,
            client_pb2.ClientBatchStatusResponse,
            validator_pb2.Message.CLIENT_BATCH_STATUS_RESPONSE,
            block_store=block_store,
            batch_cache=batch_cache)

    def _respond(self, request):
        if request.wait_for_commit:
            self._block_store.wait_for_batch_commits(
                batch_ids=request.batch_ids,
                timeout=request.timeout or DEFAULT_TIMEOUT)

        statuses = self._get_statuses(request.batch_ids)
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

        if not leaves:
            return self._wrap_response(
                self._status.NO_RESOURCE,
                head_id=head_id)

        return self._wrap_response(head_id=head_id, leaves=leaves)


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
            return self._status.MISSING_ADDRESS

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

        if not blocks:
            return self._wrap_response(
                self._status.NO_RESOURCE,
                head_id=head_id)

        return self._wrap_response(head_id=head_id, blocks=blocks)


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
        except KeyError:
            LOGGER.debug('No block "%s" in store', request.block_id)
            return self._status.NO_RESOURCE
        except TypeError:
            LOGGER.debug('"%s" is a batch is, not block', request.block_id)
            return self._status.INVALID_ID
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

        if not batches:
            return self._wrap_response(
                self._status.NO_RESOURCE,
                head_id=head_id)

        return self._wrap_response(head_id=head_id, batches=batches)


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
        except ValueError:
            LOGGER.debug('No batch "%s" in store', request.batch_id)
            return self._status.NO_RESOURCE
        except KeyError:
            LOGGER.debug('"%s" is a block id, not batch', request.batch_id)
            return self._status.INVALID_ID
        return self._wrap_response(batch=batch)

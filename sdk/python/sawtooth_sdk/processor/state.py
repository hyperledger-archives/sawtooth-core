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

from sawtooth_sdk.client.stream import MessageType

from sawtooth_protobuf import state_context_pb2


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler())
LOGGER.setLevel(logging.DEBUG)


class StateEntry(object):
    def __init__(self, address, data):
        self.address = address
        self.data = data


class State(object):
    """
    Attributes:
        _stream (sawtooth.client.stream.Stream): client grpc communication
        _context_id (str): the context_id passed in from the validator
    """
    def __init__(self, stream, context_id):
        self._stream = stream
        self._context_id = context_id

    def get(self, addresses):
        request = state_context_pb2.GetRequest(context_id=self._context_id,
                                               addresses=addresses)
        response_string = self._stream.send(
            MessageType.STATE_GET,
            request.SerializeToString()).result().content
        response = state_context_pb2.GetResponse()
        response.ParseFromString(response_string)
        entries = response.entries if response is not None else []
        LOGGER.info("Entries %s", entries)
        results = [StateEntry(address=e.address, data=e.data)
                   for e in entries if len(e.data) != 0]
        return results

    def set(self, entries):
        """
        set an address to a value in the validator's merkle state
        Args:
            entries (list): list of StateEntry

        Returns:
            addresses (list): a list of addresses that were set

        """
        state_entries = [state_context_pb2.Entry(address=e.address,
                                                 data=e.data) for e in entries]
        request = state_context_pb2.SetRequest(entries=state_entries,
                                               context_id=self._context_id)
        response = state_context_pb2.SetResponse()
        response.ParseFromString(
            self._stream.send(MessageType.STATE_SET,
                              request.SerializeToString()).result().content)
        return response.addresses

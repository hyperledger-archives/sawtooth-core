# Copyright 2016, 2017 Intel Corporation
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

from sawtooth_validator.protobuf.client_batch_submit_pb2 \
    import ClientBatchSubmitResponse
from sawtooth_validator.protobuf.validator_pb2 import Message

from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus

LOGGER = logging.getLogger(__name__)


class ClientBatchSubmitBackpressureHandler(Handler):
    """This handler receives a batch list, and accepts it if the system is
    able.  Otherwise it returns a QUEUE_FULL response.
    """

    def __init__(self, can_accept_fn):
        self._can_accept = can_accept_fn

    def handle(self, connection_id, message_content):
        if not self._can_accept():
            response = ClientBatchSubmitResponse(
                status=ClientBatchSubmitResponse.QUEUE_FULL)
            return HandlerResult(
                status=HandlerStatus.RETURN,
                message_out=response,
                message_type=Message.CLIENT_BATCH_SUBMIT_RESPONSE
            )
        return HandlerResult(status=HandlerStatus.PASS)

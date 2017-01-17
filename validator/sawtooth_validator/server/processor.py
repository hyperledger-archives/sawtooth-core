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

from sawtooth_validator.protobuf.processor_pb2 import TpRegisterResponse
from sawtooth_validator.protobuf.processor_pb2 \
    import TpRegisterRequest

from sawtooth_validator.protobuf.validator_pb2 import Message

LOGGER = logging.getLogger(__name__)


class ProcessorRegisterHandler(object):
    def __init__(self, service):
        self._service = service

    def handle(self, message, responder):
        request = TpRegisterRequest()
        request.ParseFromString(message.content)

        LOGGER.info(
            'registered transaction processor: family=%s, version=%s, '
            'encoding=%s, namepsaces=%s',
            request.family,
            request.version,
            request.encoding,
            request.namespaces)

        self._service.register_transaction_processor(
            message.sender,
            request.family,
            request.version,
            request.encoding,
            request.namespaces)

        ack = TpRegisterResponse()
        ack.status = ack.OK

        responder.send(Message(
            sender=message.sender,
            message_type=Message.TP_REGISTER_RESPONSE,
            correlation_id=message.correlation_id,
            content=ack.SerializeToString()))

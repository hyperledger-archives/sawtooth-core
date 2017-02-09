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

from sawtooth_validator.execution import processor_iterator

from sawtooth_validator.protobuf.processor_pb2 import TpRegisterResponse
from sawtooth_validator.protobuf.processor_pb2 \
    import TpRegisterRequest
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.server.dispatch import Handler
from sawtooth_validator.server.dispatch import HandlerResult
from sawtooth_validator.server.dispatch import HandlerStatus

LOGGER = logging.getLogger(__name__)


class ProcessorRegisterHandler(Handler):
    def __init__(self, processor_collection):
        self._collection = processor_collection

    def handle(self, identity, message_content):
        request = TpRegisterRequest()
        request.ParseFromString(message_content)

        LOGGER.info(
            'registered transaction processor: family=%s, version=%s, '
            'encoding=%s, namepsaces=%s',
            request.family,
            request.version,
            request.encoding,
            request.namespaces)

        processor_type = processor_iterator.ProcessorType(
            request.family,
            request.version,
            request.encoding)

        processor = processor_iterator.Processor(
            identity,
            request.namespaces)

        self._collection[processor_type] = processor

        ack = TpRegisterResponse()
        ack.status = ack.OK

        return HandlerResult(
            status=HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.TP_REGISTER_RESPONSE)

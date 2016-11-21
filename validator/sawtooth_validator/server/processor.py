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

from sawtooth_validator.server.message import Message

from sawtooth_validator.protobuf.processor_pb2 import Acknowledgement

from sawtooth_validator.protobuf.processor_pb2 \
    import TransactionProcessorRegisterRequest


class ProcessorRegisterHandler(object):
    def __init__(self, service):
        self._service = service

    def handle(self, message, responder):
        request = TransactionProcessorRegisterRequest()
        request.ParseFromString(message.content)

        print "transaction processor {} {} {} {} {}".format(
            request.family,
            request.version,
            request.encoding,
            request.namespaces,
            message.sender)

        self._service.register_transaction_processor(
            message.sender,
            request.family,
            request.version,
            request.encoding,
            request.namespaces)

        ack = Acknowledgement()
        ack.status = ack.OK

        responder.send(Message(
            message_type='common/ack',
            correlation_id=message.correlation_id,
            content=ack.SerializeToString()))

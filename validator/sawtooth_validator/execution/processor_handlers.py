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

from sawtooth_validator.execution import processor_manager

from sawtooth_validator.protobuf import processor_pb2
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus

LOGGER = logging.getLogger(__name__)

DEFAULT_MAX_OCCUPANCY = 10
# This is the version used by the SDK to match if the validator supports
# features it requested during registration. It should only be incremented
# when there are changes in TpRegisterRequest.
# Remember to sync this information in SDK if changed here.
MAX_SDK_PROTOCOL_VERSION = 1


class ProcessorRegisterValidationHandler(Handler):
    """Validates the TP Register Request and emits an Ack"""
    def handle(self, connection_id, message_content):
        request = processor_pb2.TpRegisterRequest()
        request.ParseFromString(message_content)

        # Reject the request if requested version cannot be handled,
        # validator does backward compatible support.
        if request.protocol_version > MAX_SDK_PROTOCOL_VERSION:
            ack = processor_pb2.TpRegisterResponse()
            ack.status = ack.ERROR
            ack.protocol_version = MAX_SDK_PROTOCOL_VERSION
            LOGGER.error(
                'Validator version %s does not support the features requested'
                ' by the %s version of transaction processor',
                str(MAX_SDK_PROTOCOL_VERSION),
                str(request.protocol_version))

            return HandlerResult(
                status=HandlerStatus.RETURN,
                message_out=ack,
                message_type=validator_pb2.Message.TP_REGISTER_RESPONSE)

        ack = processor_pb2.TpRegisterResponse()
        ack.status = ack.OK
        # Echo back the requested protocol_version, so that the SDK can
        # cross verify that it can get all services requested
        ack.protocol_version = request.protocol_version

        return HandlerResult(
            status=HandlerStatus.RETURN_AND_PASS,
            message_out=ack,
            message_type=validator_pb2.Message.TP_REGISTER_RESPONSE)


class ProcessorRegisterHandler(Handler):
    """Adds the Processor to the processor collection, enabling TP process
    requests"""
    def __init__(self, processor_collection):
        self._collection = processor_collection

    def handle(self, connection_id, message_content):
        request = processor_pb2.TpRegisterRequest()
        request.ParseFromString(message_content)
        if request.max_occupancy == 0:
            max_occupancy = DEFAULT_MAX_OCCUPANCY
            LOGGER.warning(
                'Max occupancy was not provided by transaction processor: %s.'
                ' Using default max occupancy: %s',
                connection_id, DEFAULT_MAX_OCCUPANCY)
        else:
            max_occupancy = request.max_occupancy

        # If the request_header_style parameter is not set in the request,
        # consider default behavior of sending EXPANDED (de-serialized) header.
        # This is for backward compatibility.
        if request.request_header_style == \
                processor_pb2.TpRegisterRequest.HEADER_STYLE_UNSET:
            header_style = processor_pb2.TpRegisterRequest.EXPANDED
        else:
            header_style = request.request_header_style

        processor_type = processor_manager.ProcessorType(
            request.family,
            request.version)

        processor = processor_manager.Processor(
            connection_id,
            request.namespaces,
            max_occupancy,
            header_style)

        self._collection[processor_type] = processor

        LOGGER.info(
            'registered transaction processor: connection_id=%s, family=%s, '
            'version=%s, namespaces=%s, max_occupancy=%s',
            connection_id,
            request.family,
            request.version,
            list(request.namespaces),
            max_occupancy)

        return HandlerResult(status=HandlerStatus.PASS)


class ProcessorUnRegisterHandler(Handler):
    def __init__(self, processor_collection):
        self._collection = processor_collection

    def handle(self, connection_id, message_content):
        request = processor_pb2.TpUnregisterRequest()
        request.ParseFromString(message_content)

        LOGGER.info("try to unregister all transaction processor "
                    "capabilities for connection_id %s", connection_id)

        self._collection.remove(processor_identity=connection_id)

        ack = processor_pb2.TpUnregisterResponse()
        ack.status = ack.OK

        return HandlerResult(
            status=HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.TP_UNREGISTER_RESPONSE)

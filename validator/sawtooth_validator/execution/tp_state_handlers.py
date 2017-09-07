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

from sawtooth_validator.protobuf import state_context_pb2
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.execution.context_manager import AuthorizationException

LOGGER = logging.getLogger(__name__)


class TpStateGetHandler(Handler):

    def __init__(self, context_manager):
        self._context_manager = context_manager

    def handle(self, connection_id, message_content):
        get_request = state_context_pb2.TpStateGetRequest()
        get_request.ParseFromString(message_content)
        try:
            return_values = self._context_manager.get(
                get_request.context_id, list(get_request.addresses))
        except AuthorizationException:
            response = \
                state_context_pb2.TpStateGetResponse(
                    status=state_context_pb2.
                    TpStateGetResponse.AUTHORIZATION_ERROR)
            return HandlerResult(
                HandlerStatus.RETURN,
                response,
                validator_pb2.Message.TP_STATE_GET_RESPONSE)

        return_list = return_values if return_values is not None else []
        LOGGER.debug("GET: %s", return_list)
        entry_list = [state_context_pb2.Entry(address=a,
                                              data=d) for a, d in return_list]
        response = state_context_pb2.TpStateGetResponse(
            status=state_context_pb2.TpStateGetResponse.OK)
        response.entries.extend(entry_list)
        return HandlerResult(
            HandlerStatus.RETURN,
            response,
            validator_pb2.Message.TP_STATE_GET_RESPONSE)


class TpStateSetHandler(Handler):
    def __init__(self, context_manager):
        """

        Args:
            context_manager (sawtooth_validator.context_manager.
            ContextManager):
        """
        self._context_manager = context_manager

    def handle(self, connection_id, message_content):
        set_request = state_context_pb2.TpStateSetRequest()
        set_request.ParseFromString(message_content)
        set_values_list = [{e.address: e.data} for e in set_request.entries]
        try:
            return_value = self._context_manager.set(set_request.context_id,
                                                     set_values_list)
        except AuthorizationException:
            response = \
                state_context_pb2.TpStateSetResponse(
                    status=state_context_pb2.
                    TpStateSetResponse.AUTHORIZATION_ERROR)
            return HandlerResult(
                HandlerStatus.RETURN,
                response,
                validator_pb2.Message.TP_STATE_SET_RESPONSE)

        response = state_context_pb2.TpStateSetResponse(
            status=state_context_pb2.TpStateSetResponse.OK)
        if return_value is True:
            address_list = [e.address for e in set_request.entries]
            LOGGER.debug("SET: %s", address_list)
            response.addresses.extend(address_list)
        else:
            LOGGER.debug("SET: No Values Set")
            response.addresses.extend([])
        return HandlerResult(
            HandlerStatus.RETURN,
            response,
            validator_pb2.Message.TP_STATE_SET_RESPONSE)


class TpStateDeleteHandler(Handler):

    def __init__(self, context_manager):
        """

        Args:
            context_manager (sawtooth_validator.context_manager.
            ContextManager):
        """
        self._context_manager = context_manager

    def handle(self, connection_id, message_content):
        delete_request = state_context_pb2.TpStateDeleteRequest()
        delete_request.ParseFromString(message_content)
        try:
            return_values = self._context_manager.delete(
                delete_request.context_id, list(delete_request.addresses))
        except AuthorizationException:
            response = \
                state_context_pb2.TpStateDeleteResponse(
                    status=state_context_pb2.
                    TpStateDeleteResponse.AUTHORIZATION_ERROR)
            return HandlerResult(
                HandlerStatus.RETURN,
                response,
                validator_pb2.Message.TP_STATE_DEL_RESPONSE)

        LOGGER.debug("DELETE: %s", return_values)
        response = state_context_pb2.TpStateDeleteResponse(
            addresses=delete_request.addresses,
            status=state_context_pb2.TpStateDeleteResponse.OK)
        return HandlerResult(
            HandlerStatus.RETURN,
            response,
            validator_pb2.Message.TP_STATE_DEL_RESPONSE)


class TpAddReceiptDataHandler(Handler):
    def __init__(self, context_manager):
        """

        Args:
            context_manager (sawtooth_validator.context_manager.
            ContextManager):
        """
        self._context_manager = context_manager

    def handle(self, connection_id, message_content):
        add_receipt_data_request = state_context_pb2.TpAddReceiptDataRequest()
        add_receipt_data_request.ParseFromString(message_content)

        LOGGER.debug("ADD RECEIPT DATA: %s", message_content)
        ack = state_context_pb2.TpAddReceiptDataResponse()
        ack.status = ack.OK

        return HandlerResult(
            status=HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.TP_ADD_RECEIPT_DATA_RESPONSE)


class TpAddEventHandler(Handler):
    def __init__(self, context_manager):
        """

        Args:
            context_manager (sawtooth_validator.context_manager.
            ContextManager):
        """
        self._context_manager = context_manager

    def handle(self, connection_id, message_content):
        add_event_request = state_context_pb2.TpAddEventRequest()
        add_event_request.ParseFromString(message_content)

        LOGGER.debug("ADD EVENT: %s", message_content)

        ack = state_context_pb2.TpAddEventResponse()
        ack.status = ack.OK

        return HandlerResult(
            status=HandlerStatus.RETURN,
            message_out=ack,
            message_type=validator_pb2.Message.TP_ADD_EVENT_RESPONSE)

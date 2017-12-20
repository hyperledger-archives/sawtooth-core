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

from sawtooth_sdk.protobuf.processor_pb2 import TpRegisterRequest
from sawtooth_sdk.protobuf.processor_pb2 import TpRegisterResponse
from sawtooth_sdk.protobuf.processor_pb2 import TpProcessResponse
from sawtooth_sdk.protobuf.processor_pb2 import TpProcessRequest

from sawtooth_sdk.protobuf.state_context_pb2 import TpStateGetResponse
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateGetRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateSetResponse
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateSetRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateDeleteRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpStateDeleteResponse
from sawtooth_sdk.protobuf.state_context_pb2 import TpEventAddRequest
from sawtooth_sdk.protobuf.state_context_pb2 import TpEventAddResponse
from sawtooth_sdk.protobuf.validator_pb2 import Message


_TYPE_TO_PROTO = {
    Message.TP_REGISTER_REQUEST: TpRegisterRequest,
    Message.TP_REGISTER_RESPONSE: TpRegisterResponse,
    Message.TP_PROCESS_RESPONSE: TpProcessResponse,
    Message.TP_PROCESS_REQUEST: TpProcessRequest,

    Message.TP_STATE_GET_REQUEST: TpStateGetRequest,
    Message.TP_STATE_GET_RESPONSE: TpStateGetResponse,
    Message.TP_STATE_SET_REQUEST: TpStateSetRequest,
    Message.TP_STATE_SET_RESPONSE: TpStateSetResponse,
    Message.TP_STATE_DELETE_REQUEST: TpStateDeleteRequest,
    Message.TP_STATE_DELETE_RESPONSE: TpStateDeleteResponse,
    Message.TP_EVENT_ADD_REQUEST: TpEventAddRequest,
    Message.TP_EVENT_ADD_RESPONSE: TpEventAddResponse,
}

_PROTO_TO_TYPE = {
    proto: type_ for type_, proto in _TYPE_TO_PROTO.items()
}


class UnknownMessageTypeException(Exception):
    pass


def to_protobuf_class(message_type):
    if message_type in _TYPE_TO_PROTO:
        return _TYPE_TO_PROTO[message_type]
    else:
        raise UnknownMessageTypeException(
            "Unknown message type: {}".format(message_type))


def to_message_type(proto):
    proto_class = proto.__class__

    if proto_class in _PROTO_TO_TYPE:
        return _PROTO_TO_TYPE[proto_class]
    else:
        raise UnknownMessageTypeException(
            "Unknown protobuf class: {}".format(proto_class))

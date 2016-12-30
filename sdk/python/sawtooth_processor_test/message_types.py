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

from sawtooth_protobuf.processor_pb2 import TransactionProcessorRegisterRequest
from sawtooth_protobuf.processor_pb2 import TransactionProcessResponse

from sawtooth_protobuf.transaction_pb2 import Transaction

from sawtooth_protobuf.state_context_pb2 import GetResponse
from sawtooth_protobuf.state_context_pb2 import GetRequest
from sawtooth_protobuf.state_context_pb2 import SetResponse
from sawtooth_protobuf.state_context_pb2 import SetRequest

_TYPE_TO_PROTO = {
    "tp/register": TransactionProcessorRegisterRequest,
    "tp/response": TransactionProcessResponse,
    "tp/request": Transaction,

    "state/getrequest": GetRequest,
    "state/getresponse": GetResponse,
    "state/setrequest": SetRequest,
    "state/setresponse": SetResponse
}

_PROTO_TO_TYPE = {
    proto: type_string for type_string, proto in _TYPE_TO_PROTO.items()
}


class UnknownMessageTypeException(Exception):
    pass


def to_protobuf_class(message_type):
    if message_type in _TYPE_TO_PROTO:
        return _TYPE_TO_PROTO[message_type]
    else:
        raise UnknownMessageTypeException(
            "Unknown message type: {}".format(message_type)
        )


def to_message_type(proto):
    proto_class = proto.__class__

    if proto_class in _PROTO_TO_TYPE:
        return _PROTO_TO_TYPE[proto_class]
    else:
        raise UnknownMessageTypeException(
            "Unknown protobuf class: {}".format(proto_class)
        )

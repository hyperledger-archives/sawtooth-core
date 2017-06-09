# Copyright 2017 Intel Corporation
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
# pylint: disable=import-error,no-name-in-module
# needed for google.protobuf import
from google.protobuf.message import DecodeError

from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.validator_pb2 import Message
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.networking.dispatch import Handler


LOGGER = logging.getLogger(__name__)


def is_batch_signer_authorized(batch, allowed_pubkeys):
    header = BatchHeader()
    header.ParseFromString(batch.header)
    if header.signer_pubkey not in allowed_pubkeys:
        LOGGER.info("Batch was signed by an unauthorized signing key %s",
                    header.signer_pubkey)
        return False
    return True


class BatchListPermissionVerifier(Handler):
    def __init__(self, settings_view_factory, current_root_func):
        self.settings_view_factory = settings_view_factory
        self.current_root_func = current_root_func

    def handle(self, connection_id, message_content):
        response_proto = client_pb2.ClientBatchSubmitResponse
        allowed_pubkeys = None
        try:
            state_root = self.current_root_func()
            settings_view = \
                self.settings_view_factory.create_settings_view(state_root)
            allowed_pubkeys = settings_view.get_setting(
                "sawtooth.validator.allowed_signing_keys")
        except AttributeError:
            LOGGER.debug("Chain head not yet set")

        def make_response(out_status):
            return HandlerResult(
                status=HandlerStatus.RETURN,
                message_out=response_proto(status=out_status),
                message_type=Message.CLIENT_BATCH_SUBMIT_RESPONSE)
        try:

            if allowed_pubkeys is not None:
                request = client_pb2.ClientBatchSubmitRequest()
                request.ParseFromString(message_content)
                if not all(is_batch_signer_authorized(batch, allowed_pubkeys)
                           for batch in request.batches):
                    return make_response(response_proto.INVALID_BATCH)
        except DecodeError:
            return make_response(response_proto.INTERNAL_ERROR)

        return HandlerResult(status=HandlerStatus.PASS)

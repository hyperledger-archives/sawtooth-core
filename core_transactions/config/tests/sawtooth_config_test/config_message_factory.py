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

from sawtooth_processor_test.message_factory import MessageFactory
from sawtooth_config.protobuf.config_pb2 import ConfigPayload
from sawtooth_config.protobuf.config_pb2 import ConfigPayload
from sawtooth_config.protobuf.config_pb2 import ConfigProposal
from sawtooth_config.protobuf.config_pb2 import ConfigVote
from sawtooth_config.protobuf.config_pb2 import SettingEntry


class ConfigMessageFactory:

    def __init__(self, private=None, public=None):
        self._factory = MessageFactory(
            encoding="application/protobuf",
            family_name="sawtooth_config",
            family_version="1.0",
            namespace="000000",
            private=private,
            public=public
        )

    @property
    def public_key(self):
        return self._factory.get_public_key()

    def _key_to_address(self, key):
        return self._factory._namespace + \
            self._factory._sha256(key.encode("utf-8"))

    def create_tp_register(self):
        return self._factory.create_tp_register()

    def create_tp_response(self, status):
        return self._factory.create_tp_response(status)

    def _create_transaction(self, setting, payload):
        inputs = [
            self._key_to_address('sawtooth.config.authorization_type'),
            self._key_to_address('sawtooth.config.vote.proposals'),
            self._key_to_address('sawtooth.config.vote.authorized_keys'),
            self._key_to_address('sawtooth.config.vote.approval_threshold'),
            self._key_to_address(setting)
        ]

        outputs = [
            self._key_to_address('sawtooth.config.vote.proposals'),
            self._key_to_address(setting)
        ]

        return self._factory.create_transaction(
            payload.SerializeToString(), inputs, outputs, [])

    def create_proposal_transaction(self, setting, value, nonce):
        proposal = ConfigProposal(setting=setting, value=value, nonce=nonce)
        payload = ConfigPayload(action=ConfigPayload.PROPOSE,
                                data=proposal.SerializeToString())

        return self._create_transaction(setting, payload)

    def create_vote_proposal(self, proposal_id, setting, vote):
        vote = ConfigVote(proposal_id=proposal_id, vote=vote)
        payload = ConfigPayload(action=ConfigPayload.VOTE,
                                data=vote.SerializeToString())

        return self._create_transaction(setting, payload)

    def create_get_request(self, setting):
        addresses = [self._key_to_address(setting)]
        return self._factory.create_get_request(addresses)

    def create_get_response(self, setting, value=None):
        address = self._key_to_address(setting)

        if value is not None:
            data = SettingEntry(values={setting: value}).SerializeToString()
        else:
            data = None

        return self._factory.create_get_response({address: data})

    def create_set_request(self, setting, value=None):
        address = self._key_to_address(setting)

        if value is not None:
            data = SettingEntry(values={setting: value}).SerializeToString()
        else:
            data = None

        return self._factory.create_set_request({address: data})

    def create_set_response(self, setting):
        addresses = [self._key_to_address(setting)]
        return self._factory.create_set_response(addresses)

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
from sawtooth_settings.protobuf.settings_pb2 import SettingsPayload
from sawtooth_settings.protobuf.settings_pb2 import SettingProposal
from sawtooth_settings.protobuf.settings_pb2 import SettingVote
from sawtooth_settings.protobuf.setting_pb2 import Setting

_MAX_KEY_PARTS = 4
_ADDRESS_PART_SIZE = 16


class SettingsMessageFactory:
    def __init__(self, signer=None):
        self._factory = MessageFactory(
            family_name="sawtooth_settings",
            family_version="1.0",
            namespace="000000",
            signer=signer)

    @property
    def public_key(self):
        return self._factory.get_public_key()

    def _key_to_address(self, key):
        key_parts = key.split('.', maxsplit=_MAX_KEY_PARTS - 1)
        key_parts.extend([''] * (_MAX_KEY_PARTS - len(key_parts)))

        def _short_hash(in_str):
            return self._factory.sha256(in_str.encode())[:16]

        return self._factory.namespace + \
            ''.join(_short_hash(x) for x in key_parts)

    def create_tp_register(self):
        return self._factory.create_tp_register()

    def create_tp_response(self, status):
        return self._factory.create_tp_response(status)

    def _create_tp_process_request(self, setting, payload):
        inputs = [
            self._key_to_address('sawtooth.settings.vote.proposals'),
            self._key_to_address('sawtooth.settings.vote.authorized_keys'),
            self._key_to_address('sawtooth.settings.vote.approval_threshold'),
            self._key_to_address(setting)
        ]

        outputs = [
            self._key_to_address('sawtooth.settings.vote.proposals'),
            self._key_to_address(setting)
        ]

        return self._factory.create_tp_process_request(
            payload.SerializeToString(), inputs, outputs, [])

    def create_proposal_transaction(self, setting, value, nonce):
        proposal = SettingProposal(setting=setting, value=value, nonce=nonce)
        payload = SettingsPayload(action=SettingsPayload.PROPOSE,
                                  data=proposal.SerializeToString())

        return self._create_tp_process_request(setting, payload)

    def create_vote_proposal(self, proposal_id, setting, vote):
        vote = SettingVote(proposal_id=proposal_id, vote=vote)
        payload = SettingsPayload(action=SettingsPayload.VOTE,
                                  data=vote.SerializeToString())

        return self._create_tp_process_request(setting, payload)

    def create_get_request(self, setting):
        addresses = [self._key_to_address(setting)]
        return self._factory.create_get_request(addresses)

    def create_get_response(self, setting, value=None):
        address = self._key_to_address(setting)

        if value is not None:
            entry = Setting.Entry(key=setting, value=value)
            data = Setting(entries=[entry]).SerializeToString()
        else:
            data = None

        return self._factory.create_get_response({address: data})

    def create_set_request(self, setting, value=None):
        address = self._key_to_address(setting)

        if value is not None:
            entry = Setting.Entry(key=setting, value=value)
            data = Setting(entries=[entry]).SerializeToString()
        else:
            data = None

        return self._factory.create_set_request({address: data})

    def create_set_response(self, setting):
        addresses = [self._key_to_address(setting)]
        return self._factory.create_set_response(addresses)

    def create_add_event_request(self, key):
        return self._factory.create_add_event_request(
            "settings/update",
            [("updated", key)])

    def create_add_event_response(self):
        return self._factory.create_add_event_response()

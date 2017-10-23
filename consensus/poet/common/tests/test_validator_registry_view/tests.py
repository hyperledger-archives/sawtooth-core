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
import unittest

from sawtooth_poet_common.protobuf.validator_registry_pb2 import ValidatorInfo
from sawtooth_poet_common.protobuf.validator_registry_pb2 import SignUpInfo
from sawtooth_poet_common.validator_registry_view.validator_registry_view \
    import ValidatorRegistryView

from test_validator_registry_view.mocks import MockStateView
from test_validator_registry_view.utils import to_address


class TestValidatorRegistryView(unittest.TestCase):

    def test_get_validator_info(self):
        """Given a state view that contains a state entry for a given validator
        info, verify that the validator registry returns a ValidatorInfo when
        get_validator_info is called with the validator's id."""

        state_view = MockStateView({
            to_address('my_id'): ValidatorInfo(
                name='my_validator',
                id='my_id',
                signup_info=SignUpInfo(poet_public_key='my_public_key',
                                       proof_data='beleive me',
                                       anti_sybil_id='no sybil'),
                transaction_id="signature"
            ).SerializeToString()
        })
        validator_registry_view = ValidatorRegistryView(state_view)

        info = validator_registry_view.get_validator_info('my_id')
        self.assertEqual('my_id', info.id)
        self.assertEqual('my_validator', info.name)
        self.assertEqual("signature", info.transaction_id)
        self.assertEqual('my_public_key', info.signup_info.poet_public_key)
        self.assertEqual('beleive me', info.signup_info.proof_data)
        self.assertEqual('no sybil', info.signup_info.anti_sybil_id)

    def test_get_validator_info_not_exists(self):
        """Given a state view that does not contain a state view for a given
        validator info, verify that it throws a key error on `get`.
        """
        state_view = MockStateView({})
        validator_registry_view = ValidatorRegistryView(state_view)

        with self.assertRaises(KeyError):
            validator_registry_view.get_validator_info('my_id')

    def test_has_validator_info(self):
        """Given a state view that contains a state entry for a given validator
        info, verify that the validator registry returns a true when
        has_validator_info is called with the validator's id."""

        state_view = MockStateView({
            to_address('my_id'): ValidatorInfo(
                name='my_validator',
                id='my_id',
                signup_info=SignUpInfo(poet_public_key='my_public_key',
                                       proof_data='beleive me',
                                       anti_sybil_id='no sybil'),
                transaction_id="signature"
            ).SerializeToString()
        })
        validator_registry_view = ValidatorRegistryView(state_view)

        self.assertTrue(validator_registry_view.has_validator_info('my_id'))

    def test_has_validator_info_not_exists(self):
        """Given a state view that does not contain a state view for a given
        validator info, verify that has_validator_info returns False with an
        unkown id.
        """
        state_view = MockStateView({})
        validator_registry_view = ValidatorRegistryView(state_view)

        self.assertFalse(validator_registry_view.has_validator_info('my_id'))

    def test_get_validators(self):
        """Given a state view with multiple validators, and the 'validator_map'
        entry, verify that get_validators returns the list of just
        ValidatorInfo instances.
        """
        state_view = MockStateView({
            to_address('validator_map'): b'this should be ignored',
            to_address('my_id'): ValidatorInfo(
                name='my_validator',
                id='my_id',
                signup_info=SignUpInfo(poet_public_key='my_public_key',
                                       proof_data='beleive me',
                                       anti_sybil_id='no sybil'),
                transaction_id="signature"
            ).SerializeToString(),
            to_address('another_id'): ValidatorInfo(
                name='your_validator',
                id='another_id',
                signup_info=SignUpInfo(poet_public_key='your_public_key',
                                       proof_data='you betcha',
                                       anti_sybil_id='poor sybil'),
                transaction_id="signature"
            ).SerializeToString()
        })

        validator_registry_view = ValidatorRegistryView(state_view)

        infos = validator_registry_view.get_validators()
        self.assertEqual(2, len(infos))
        self.assertEqual('my_validator', infos['my_id'].name)
        self.assertEqual('your_validator', infos['another_id'].name)

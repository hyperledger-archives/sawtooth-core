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

import unittest

from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator.\
    enclave_signup_info import EnclaveSignupInfo


class TestEnclaveSimulatorSignupInfo(unittest.TestCase):

    def test_create_signup_info(self):
        signup_info = \
            EnclaveSignupInfo(
                poet_public_key='My Fake Key',
                proof_data='I am Victoria Antoinette Scharleau, and I '
                           'approve of this message.',
                anti_sybil_id='Sally Field',
                sealed_signup_data="Signed, Sealed, Delivered, I'm Yours")
        self.assertEqual(signup_info.poet_public_key, 'My Fake Key')
        self.assertEqual(
            signup_info.proof_data,
            'I am Victoria Antoinette Scharleau, and I approve of this '
            'message.')
        self.assertEqual(signup_info.anti_sybil_id, 'Sally Field')
        self.assertEqual(
            signup_info.sealed_signup_data,
            "Signed, Sealed, Delivered, I'm Yours")

    def test_serialize_signup_info(self):
        signup_info = \
            EnclaveSignupInfo(
                poet_public_key='My Fake Key',
                proof_data='I am Victoria Antoinette Scharleau, and I '
                           'approve of this message.',
                anti_sybil_id='Sally Field',
                sealed_signup_data="Signed, Sealed, Delivered, I'm Yours")

        self.assertIsNotNone(signup_info.serialize())

    def test_deserialized_signup_info(self):
        signup_info = \
            EnclaveSignupInfo(
                poet_public_key='My Fake Key',
                proof_data='I am Victoria Antoinette Scharleau, and I '
                           'approve of this message.',
                anti_sybil_id='Sally Field',
                sealed_signup_data="Signed, Sealed, Delivered, I'm Yours")
        serialized = signup_info.serialize()
        copy_signup_info = \
            EnclaveSignupInfo.signup_info_from_serialized(serialized)

        self.assertEqual(
            signup_info.poet_public_key,
            copy_signup_info.poet_public_key)
        self.assertEqual(signup_info.proof_data, copy_signup_info.proof_data)
        self.assertEqual(
            signup_info.anti_sybil_id,
            copy_signup_info.anti_sybil_id)
        self.assertIsNone(copy_signup_info.sealed_signup_data)
        self.assertEqual(serialized, copy_signup_info.serialize())

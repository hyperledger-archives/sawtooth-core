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

from sawtooth_identity_test.identity_message_factory \
    import IdentityMessageFactory

from sawtooth_processor_test.transaction_processor_test_case \
    import TransactionProcessorTestCase

# Address for Setting: "sawtooth.identity.allowed_keys"
ALLOWED_SIGNER_ADDRESS = \
    "000000a87cb5eafdcca6a8689f6a627384c7dcf91e6901b1da081ee3b0c44298fc1c14"


class TestIdentity(TransactionProcessorTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = IdentityMessageFactory()

    def _expect_setting_get(self, key, allowed=True):
        recieved = self.validator.expect(
            self.factory.create_get_setting_request(key))

        self.validator.respond(
            self.factory.create_get_setting_response(key, allowed),
            recieved)

    def _expect_policy_get(self, key, value=None):
        recieved = self.validator.expect(
            self.factory.create_get_policy_request(key))

        self.validator.respond(
            self.factory.create_get_policy_response(key, value),
            recieved)

    def _expect_role_get(self, key=None, value=None):
        recieved = self.validator.expect(
            self.factory.create_get_role_request(key))

        self.validator.respond(
            self.factory.create_get_role_response(key, value),
            recieved)

    def _expect_policy_set(self, key, expected_value):
        recieved = self.validator.expect(
            self.factory.create_set_policy_request(key, expected_value))

        self.validator.respond(
            self.factory.create_set_policy_response(key),
            recieved)

    def _expect_role_set(self, key, value):
        recieved = self.validator.expect(
            self.factory.create_set_role_request(key, value))

        self.validator.respond(
            self.factory.create_set_role_response(key),
            recieved)

    def _expect_add_event(self, key):
        recieved = self.validator.expect(
            self.factory.create_add_event_request(key))

        self.validator.respond(
            self.factory.create_add_event_response(),
            recieved)

    def _expect_ok(self):
        self.validator.expect(self.factory.create_tp_response("OK"))

    def _expect_invalid_transaction(self):
        self.validator.expect(
            self.factory.create_tp_response("INVALID_TRANSACTION"))

    def _expect_internal_error(self):
        self.validator.expect(
            self.factory.create_tp_response("INTERNAL_ERROR"))

    def _role(self, name, policy_name):
        self.validator.send(self.factory.create_role_transaction(
            name, policy_name))

    def _policy(self, name, declarations):
        self.validator.send(
            self.factory.create_policy_transaction(name, declarations))

    @property
    def _public_key(self):
        return self.factory.public_key

    def test_set_policy(self):
        """
        Tests setting a valid policy.
        """
        self._policy("policy1", "PERMIT_KEY *")
        self._expect_setting_get(ALLOWED_SIGNER_ADDRESS)
        self._expect_policy_get("policy1")
        self._expect_policy_set("policy1", "PERMIT_KEY *")
        self._expect_add_event("policy1")
        self._expect_ok()

    def test_set_role(self):
        """
        Tests setting a valid role.
        """
        self._role("role1", "policy1")
        self._expect_setting_get(ALLOWED_SIGNER_ADDRESS)
        self._expect_policy_get("policy1", "PERMIT_KEY *")
        self._expect_role_get("role1")
        self._expect_role_set("role1", "policy1")
        self._expect_add_event("role1")
        self._expect_ok()

    def test_set_role_bad_signer(self):
        self._role("role1", "policy1")
        self._expect_setting_get(ALLOWED_SIGNER_ADDRESS, False)
        self._expect_invalid_transaction()

    def test_set_role_without_policy(self):
        """
        Tests setting a invalid role, where the policy does not exist. This
        should return an invalid transaction.
        """
        self._role("role1", "policy1")
        self._expect_setting_get(ALLOWED_SIGNER_ADDRESS)
        self._expect_policy_get("policy1")
        self._expect_invalid_transaction()

    def test_set_role_without_policy_name(self):
        """
        Tests setting a invalid role, where no policy name is set. This should
        return an invalid transaction.
        """
        self._role("role1", "")
        self._expect_setting_get(ALLOWED_SIGNER_ADDRESS)
        self._expect_invalid_transaction()

    def test_set_role_without_name(self):
        """
        Tests setting a invalid role, where no role name is set. This should
        return an invalid transaction.
        """
        self._role("", "policy1")
        self._expect_setting_get(ALLOWED_SIGNER_ADDRESS)
        self._expect_invalid_transaction()

    def test_set_policy_without_entries(self):
        """
        Tests setting a invalid policy, where no entries are set. This
        should return an invalid transaction.
        """
        self._policy("policy1", "")
        self._expect_setting_get(ALLOWED_SIGNER_ADDRESS)
        self._expect_invalid_transaction()

    def test_set_policy_without_name(self):
        """
        Tests setting a invalid role, where no policy name is set. This should
        return an invalid transaction.
        """
        self._policy("", "PERMIT_KEY *")
        self._expect_setting_get(ALLOWED_SIGNER_ADDRESS)
        self._expect_invalid_transaction()

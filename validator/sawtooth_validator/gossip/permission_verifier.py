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

from google.protobuf.message import DecodeError

from sawtooth_validator.protobuf import client_pb2
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.validator_pb2 import Message
from sawtooth_validator.protobuf.identity_pb2 import Policy
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.state.merkle import INIT_ROOT_KEY


LOGGER = logging.getLogger(__name__)


class PermissionVerifier(object):

    def __init__(self, identity_view_factory, permissions, current_root_func):
        self._identity_view_factory = identity_view_factory
        # Off-chain permissions to be enforced
        self._permissions = permissions
        self._current_root_func = current_root_func

    def is_batch_signer_authorized(self, batch, state_root=None):
        """ Check the batch signing key against the allowed transactor
            permissions. The roles being checked are the following, from first
            to last:
                "transactor.batch_signer"
                "transactor"
                "default"

            The first role that is set will be the one used to enforce if the
            batch signer is allowed.

            Args:
                batch (Batch): The batch that is being verified.
                state_root(string): The state root of the previous block. If
                    this is None, the current state root hash will be
                    retrieved.
        """
        if state_root is None:
            state_root = self._current_root_func()
            if state_root == INIT_ROOT_KEY:
                LOGGER.debug("Chain head is not set yet. Permit all.")
                return True

        identity_view = \
            self._identity_view_factory.create_identity_view(state_root)

        header = BatchHeader()
        header.ParseFromString(batch.header)

        role = \
            identity_view.get_role("transactor.batch_signer")

        if role is None:
            role = identity_view.get_role("transactor")

        if role is None:
            policy_name = "default"
        else:
            policy_name = role.policy_name

        policy = identity_view.get_policy(policy_name)
        if policy is None:
            allowed = True
        else:
            allowed = self._allowed(header.signer_pubkey, policy)

        if allowed:
            return self.is_transaction_signer_authorized(
                        batch.transactions,
                        identity_view)
        LOGGER.debug("Batch Signer: %s is not permitted.",
                     header.signer_pubkey)
        return False

    def is_transaction_signer_authorized(self, transactions, identity_view):
        """ Check the transaction signing key against the allowed transactor
            permissions. The roles being checked are the following, from first
            to last:
                "transactor.transaction_signer.<TP_Name>"
                "transactor.transaction_signer"
                "transactor"
                "default"

            The first role that is set will be the one used to enforce if the
            transaction signer is allowed.

            Args:
                transactions (List of Transactions): The transactions that are
                    being verified.
                identity_view (IdentityView): The IdentityView that should be
                    used to verify the transactions.
        """
        role = None
        if role is None:
            role = identity_view.get_role(
                "transactor.transaction_signer")

        if role is None:
            role = identity_view.get_role("transactor")

        if role is None:
            policy_name = "default"
        else:
            policy_name = role.policy_name

        policy = identity_view.get_policy(policy_name)

        family_roles = {}
        for transaction in transactions:
            header = TransactionHeader()
            header.ParseFromString(transaction.header)
            family_policy = None
            if header.family_name not in family_roles:
                role = identity_view.get_role(
                    "transactor.transaction_signer." + header.family_name)

                if role is not None:
                    family_policy = identity_view.get_policy(role.policy_name)
                family_roles[header.family_name] = family_policy
            else:
                family_policy = family_roles[header.family_name]

            if family_policy is not None:
                if not self._allowed(header.signer_pubkey, family_policy):
                    LOGGER.debug("Transaction Signer: %s is not permitted.",
                                 header.signer_pubkey)
                    return False
            else:
                if policy is not None:
                    if not self._allowed(header.signer_pubkey, policy):
                        LOGGER.debug(
                            "Transaction Signer: %s is not permitted.",
                            header.signer_pubkey)
                        return False
        return True

    def check_off_chain_batch_roles(self, batch):
        """ Check the batch signing key against the allowed off-chain
            transactor permissions. The roles being checked are the following,
            from first to last:
                "transactor.batch_signer"
                "transactor"

            The first role that is set will be the one used to enforce if the
            batch signer is allowed.

            Args:
                batch (Batch): The batch that is being verified.
                state_root(string): The state root of the previous block. If
                    this is None, the current state root hash will be
                    retrieved.
        """
        if self._permissions is None:
            return True
        header = BatchHeader()
        header.ParseFromString(batch.header)
        policy = None
        if "transactor.batch_signer" in self._permissions:
            policy = self._permissions["transactor.batch_signer"]

        elif "transactor" in self._permissions:
            policy = self._permissions["transactor"]

        allowed = True
        if policy is not None:
            allowed = self._allowed(header.signer_pubkey, policy)

        if allowed:
            return self.check_off_chain_transaction_roles(batch.transactions)

        LOGGER.debug("Batch Signer: %s is not permitted by local"
                     " configuration.", header.signer_pubkey)
        return False

    def check_off_chain_transaction_roles(self, transactions):
        """ Check the transaction signing key against the allowed off-chain
            transactor permissions. The roles being checked are the following,
            from first to last:
                "transactor.transaction_signer.<TP_Name>"
                "transactor.transaction_signer"
                "transactor"

            The first role that is set will be the one used to enforce if the
            transaction signer is allowed.

            Args:
                transactions (List of Transactions): The transactions that are
                    being verified.
                identity_view (IdentityView): The IdentityView that should be
                    used to verify the transactions.
        """
        policy = None
        if "transactor.transaction_signer" in self._permissions:
            policy = self._permissions["transactor.transaction_signer"]

        elif "transactor" in self._permissions:
            policy = self._permissions["transactor"]

        for transaction in transactions:
            header = TransactionHeader()
            header.ParseFromString(transaction.header)
            family_role = "transactor.transaction_signer." + \
                header.family_name
            family_policy = None
            if family_role in self._permissions:
                family_policy = self._permissions[family_role]

            if family_policy is not None:
                if not self._allowed(header.signer_pubkey, family_policy):
                    LOGGER.debug("Transaction Signer: %s is not permitted"
                                 "by local configuration.",
                                 header.signer_pubkey)
                    return False

            elif policy is not None:
                if not self._allowed(header.signer_pubkey, policy):
                    LOGGER.debug("Transaction Signer: %s is not permitted"
                                 "by local configuration.",
                                 header.signer_pubkey)
                    return False

        return True

    def _allowed(self, public_key, policy):
        for entry in policy.entries:
            if entry.type == Policy.PERMIT_KEY:
                if public_key == entry.key or entry.key == "*":
                    return True

            elif entry.type == Policy.DENY_KEY:

                if public_key == entry.key or entry.key == "*":
                    return False

        # Default last entry is always DENY all
        return False


class BatchListPermissionVerifier(Handler):
    def __init__(self, permission_verifier):
        self._verifier = permission_verifier

    def handle(self, connection_id, message_content):
        response_proto = client_pb2.ClientBatchSubmitResponse

        def make_response(out_status):
            return HandlerResult(
                status=HandlerStatus.RETURN,
                message_out=response_proto(status=out_status),
                message_type=Message.CLIENT_BATCH_SUBMIT_RESPONSE)
        try:
            request = client_pb2.ClientBatchSubmitRequest()
            request.ParseFromString(message_content)
            if not all(self._verifier.check_off_chain_batch_roles(batch)
                       for batch in request.batches):
                return make_response(response_proto.INVALID_BATCH)

            if not all(self._verifier.is_batch_signer_authorized(batch)
                       for batch in request.batches):
                return make_response(response_proto.INVALID_BATCH)

        except DecodeError:
            return make_response(response_proto.INTERNAL_ERROR)

        return HandlerResult(status=HandlerStatus.PASS)

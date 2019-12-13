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

from sawtooth_validator.protobuf import client_batch_submit_pb2
from sawtooth_validator.protobuf.batch_pb2 import BatchHeader
from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader
from sawtooth_validator.protobuf.validator_pb2 import Message
from sawtooth_validator.protobuf.identity_pb2 import Policy
from sawtooth_validator.protobuf.authorization_pb2 import \
    AuthorizationViolation
from sawtooth_validator.protobuf.authorization_pb2 import RoleType
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf.network_pb2 import GossipMessage
from sawtooth_validator.protobuf.block_pb2 import BlockHeader
from sawtooth_validator.networking.dispatch import HandlerResult
from sawtooth_validator.networking.dispatch import HandlerStatus
from sawtooth_validator.networking.dispatch import Handler
from sawtooth_validator.state.merkle import INIT_ROOT_KEY


LOGGER = logging.getLogger(__name__)


class _LogGuard:
    def __init__(self):
        self.chain_head_not_yet_set = False


class PermissionVerifier:
    def __init__(self, permissions, current_root_func, identity_cache):
        # Off-chain permissions to be enforced
        self._permissions = permissions
        self._chain_head_set = False
        self._current_root_func = current_root_func
        self._cache = identity_cache
        self._log_guard = _LogGuard()

    # pylint: disable=function-redefined
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
                state_root(string): The state root of the previous block; if
                    this is specified, do not read cached values. If this is
                    None, the current state root hash and cached values will be
                    used.

        """
        if state_root is None:
            state_root_func = self._current_root_func
            from_state = False
            if not self._chain_head_set:
                if self._current_root_func() == INIT_ROOT_KEY:
                    if not self._log_guard.chain_head_not_yet_set:
                        LOGGER.debug("Chain head is not set yet. Permit all.")
                        self._log_guard.chain_head_not_yet_set = True
                    return True
                self._chain_head_set = True
        else:
            def state_root_func():
                return state_root
            from_state = True

        self._cache.update_view(state_root_func())

        header = BatchHeader()
        header.ParseFromString(batch.header)

        role = self._cache.get_role(
            "transactor.batch_signer",
            state_root_func,
            from_state)

        if role is None:
            role = self._cache.get_role(
                "transactor", state_root_func, from_state)

        if role is None:
            policy_name = "default"
        else:
            policy_name = role.policy_name

        policy = self._cache.get_policy(
            policy_name, state_root_func, from_state)
        if policy is None:
            allowed = True
        else:
            allowed = self._allowed(header.signer_public_key, policy)

        if allowed:
            return self.is_transaction_signer_authorized(
                batch.transactions,
                state_root_func,
                from_state)
        LOGGER.debug("Batch Signer: %s is not permitted.",
                     header.signer_public_key)
        return False

    def is_transaction_signer_authorized(self, transactions, state_root_func,
                                         from_state):
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
                state_root_func(fn -> string): The state root of the previous
                    block. If this is None, the current state root hash will be
                    retrieved.
                from_state (bool): Whether the identity value should be read
                    directly from state, instead of using the cached values.
                    This should be used when the state_root_func passed is not
                    from the current chain head.
        """
        role = None
        if role is None:
            role = self._cache.get_role("transactor.transaction_signer",
                                        state_root_func, from_state)

        if role is None:
            role = self._cache.get_role(
                "transactor", state_root_func, from_state)

        if role is None:
            policy_name = "default"
        else:
            policy_name = role.policy_name

        policy = self._cache.get_policy(
            policy_name, state_root_func, from_state)

        family_roles = {}
        for transaction in transactions:
            header = TransactionHeader()
            header.ParseFromString(transaction.header)
            family_policy = None
            if header.family_name not in family_roles:
                role = self._cache.get_role(
                    "transactor.transaction_signer." + header.family_name,
                    state_root_func,
                    from_state)

                if role is not None:
                    family_policy = self._cache.get_policy(role.policy_name,
                                                           state_root_func,
                                                           from_state)
                family_roles[header.family_name] = family_policy
            else:
                family_policy = family_roles[header.family_name]

            if family_policy is not None:
                if not self._allowed(header.signer_public_key, family_policy):
                    LOGGER.debug("Transaction Signer: %s is not permitted.",
                                 header.signer_public_key)
                    return False
            else:
                if policy is not None:
                    if not self._allowed(header.signer_public_key, policy):
                        LOGGER.debug(
                            "Transaction Signer: %s is not permitted.",
                            header.signer_public_key)
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
            allowed = self._allowed(header.signer_public_key, policy)

        if allowed:
            return self.check_off_chain_transaction_roles(batch.transactions)

        LOGGER.debug("Batch Signer: %s is not permitted by local"
                     " configuration.", header.signer_public_key)
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
                if not self._allowed(header.signer_public_key, family_policy):
                    LOGGER.debug("Transaction Signer: %s is not permitted"
                                 "by local configuration.",
                                 header.signer_public_key)
                    return False

            elif policy is not None:
                if not self._allowed(header.signer_public_key, policy):
                    LOGGER.debug("Transaction Signer: %s is not permitted"
                                 "by local configuration.",
                                 header.signer_public_key)
                    return False

        return True

    def check_network_role(self, public_key):
        """ Check the public key of a node on the network to see if they are
            permitted to participate. The roles being checked are the
            following, from first to last:
                "network"
                "default"

            The first role that is set will be the one used to enforce if the
            node is allowed.

            Args:
                public_key (string): The public key belonging to a node on the
                    network
        """
        state_root = self._current_root_func()
        if state_root == INIT_ROOT_KEY:
            if not self._log_guard.chain_head_not_yet_set:
                LOGGER.debug("Chain head is not set yet. Permit all.")
                self._log_guard.chain_head_not_yet_set = True
            return True

        self._cache.update_view(state_root)
        role = self._cache.get_role("network", self._current_root_func, True)

        if role is None:
            policy_name = "default"
        else:
            policy_name = role.policy_name
        policy = self._cache.get_policy(
            policy_name, self._current_root_func, True)
        if policy is not None:
            if not self._allowed(public_key, policy):
                LOGGER.debug("Node is not permitted: %s.", public_key)
                return False
        return True

    def check_network_consensus_role(self, public_key):
        """ Check the public key of a node on the network to see if they are
            permitted to publish blocks. The roles being checked are the
            following, from first to last:
                "network.consensus"
                "default"

            The first role that is set will be the one used to enforce if the
            node is allowed to publish blocks.

            Args:
                public_key (string): The public key belonging to a node on the
                    network
        """
        state_root = self._current_root_func()
        self._cache.update_view(state_root)
        role = self._cache.get_role(
            "network.consensus", self._current_root_func, True)

        if role is None:
            policy_name = "default"
        else:
            policy_name = role.policy_name
        policy = self._cache.get_policy(
            policy_name, self._current_root_func, True)
        if policy is not None:
            if not self._allowed(public_key, policy):
                LOGGER.debug(
                    "Node is not permitted to publish blocks: %s.",
                    public_key)
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
        response_proto = client_batch_submit_pb2.ClientBatchSubmitResponse

        def make_response(out_status):
            return HandlerResult(
                status=HandlerStatus.RETURN,
                message_out=response_proto(status=out_status),
                message_type=Message.CLIENT_BATCH_SUBMIT_RESPONSE)

        for batch in message_content.batches:
            if batch.trace:
                LOGGER.debug("TRACE %s: %s", batch.header_signature,
                             self.__class__.__name__)
        if not all(
                self._verifier.check_off_chain_batch_roles(batch)
                for batch in message_content.batches):
            return make_response(response_proto.INVALID_BATCH)

        if not all(
                self._verifier.is_batch_signer_authorized(batch)
                for batch in message_content.batches):
            return make_response(response_proto.INVALID_BATCH)

        return HandlerResult(status=HandlerStatus.PASS)


class NetworkPermissionHandler(Handler):
    def __init__(self, network, permission_verifier, gossip):
        self._network = network
        self._permission_verifier = permission_verifier
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        # check to see if there is a public key
        public_key = self._network.connection_id_to_public_key(connection_id)

        if public_key is None:
            LOGGER.warning("No public key found, %s is not permitted. "
                           "Close connection.", connection_id)
            violation = AuthorizationViolation(
                violation=RoleType.Value("NETWORK"))
            self._gossip.unregister_peer(connection_id)
            return HandlerResult(
                HandlerStatus.RETURN_AND_CLOSE,
                message_out=violation,
                message_type=validator_pb2.Message.AUTHORIZATION_VIOLATION)

        # check public key against network/default role
        permitted = self._permission_verifier.check_network_role(public_key)

        if not permitted:
            LOGGER.debug("Public key not permitted, %s is not permitted",
                         connection_id)
            self._gossip.unregister_peer(connection_id)
            violation = AuthorizationViolation(
                violation=RoleType.Value("NETWORK"))
            return HandlerResult(
                HandlerStatus.RETURN_AND_CLOSE,
                message_out=violation,
                message_type=validator_pb2.Message.AUTHORIZATION_VIOLATION)

        # if allowed pass message
        return HandlerResult(HandlerStatus.PASS)


class NetworkConsensusPermissionHandler(Handler):
    def __init__(self, network, permission_verifier, gossip):
        self._network = network
        self._permission_verifier = permission_verifier
        self._gossip = gossip

    def handle(self, connection_id, message_content):
        obj, tag, _ = message_content

        if tag == GossipMessage.BLOCK:
            public_key = \
                self._network.connection_id_to_public_key(connection_id)
            header = BlockHeader()
            header.ParseFromString(obj.header)
            if header.signer_public_key == public_key:
                permitted = \
                    self._permission_verifier.check_network_consensus_role(
                        public_key)
                if not permitted:
                    LOGGER.debug(
                        "Public key is not permitted to publish block, "
                        "remove connection: %s", connection_id)
                    self._gossip.unregister_peer(connection_id)
                    violation = AuthorizationViolation(
                        violation=RoleType.Value("NETWORK"))
                    return HandlerResult(
                        HandlerStatus.RETURN_AND_CLOSE,
                        message_out=violation,
                        message_type=validator_pb2.Message.
                        AUTHORIZATION_VIOLATION)

        # if allowed pass message
        return HandlerResult(HandlerStatus.PASS)


class IdentityCache():
    def __init__(self, identity_view_factory):
        self._identity_view_factory = identity_view_factory
        self._identity_view = None
        self._cache = {}

    def __len__(self):
        return len(self._cache)

    def __contains__(self, item):
        return item in self._cache

    def __getitem__(self, item):
        return self._cache.get(item)

    def __iter__(self):
        return iter(self._cache)

    def get_role(self, item, state_root_func, from_state=False):
        """
        Used to retrieve an identity role.
        Args:
            item (string): the name of the role to be fetched
            state_root_func(fn -> string): The state root of the previous block
            from_state (bool): Whether the identity value should be read
                directly from state, instead of using the cached values.
                This should be used when the state_root passed is not from
                the current chain head.
        """
        if from_state:
            # if from state use identity_view and do not add to cache
            if self._identity_view is None:
                self.update_view(state_root_func())
            value = self._identity_view.get_role(item)
            return value

        value = self._cache.get(item)
        if value is None:
            if self._identity_view is None:
                self.update_view(state_root_func())
            value = self._identity_view.get_role(item)
            self._cache[item] = value
        return value

    def get_policy(self, item, state_root_func, from_state=False):
        """
        Used to retrieve an identity policy.
        Args:
            item (string): the name of the policy to be fetched
            state_root_func(fn -> string): The state root of the previous block
            from_state (bool): Whether the identity value should be read
                directly from state, instead of using the cached values.
                This should be used when the state_root passed is not from
                the current chain head.
        """
        if from_state:
            # if from state use identity_view and do not add to cache
            if self._identity_view is None:
                self.update_view(state_root_func())
            value = self._identity_view.get_policy(item)
            return value

        if item in self._cache:
            value = self._cache.get(item)
        else:
            if self._identity_view is None:
                self.update_view(state_root_func())
            value = self._identity_view.get_policy(item)
            self._cache[item] = value
        return value

    def forked(self):
        self._cache = {}

    def invalidate(self, item):
        if item in self._cache:
            del self._cache[item]

    def update_view(self, state_root):
        self._identity_view = \
            self._identity_view_factory.create_identity_view(state_root)

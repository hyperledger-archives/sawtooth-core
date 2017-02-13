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

import logging
import hashlib

from sawtooth_signing import pbct as signing
from journal import transaction
from journal import object_store
from journal.messages import transaction_message
from sawtooth_validator.consensus.poet1.signup_info import SignupInfo

from gossip.common import NullIdentifier
from sawtooth.exceptions import InvalidTransactionError

LOGGER = logging.getLogger(__name__)


def register_transaction_types(journal):
    """Registers the validator registry transaction types on the ledger.

    Args:
        ledger (journal.journal_core.Journal): The ledger to register
            the transaction type against.
    """
    journal.dispatcher.register_message_handler(
        ValidatorRegistryTransactionMessage,
        transaction_message.transaction_message_handler)
    journal.add_transaction_store(ValidatorRegistryTransaction)


class ValidatorRegistryTransactionMessage(
        transaction_message.TransactionMessage):
    """Validator registry transaction messages represent validator
    registry transactions.

    Attributes:
        ValidatorRegistryTransactionMessage.MessageType (str): The class name
            of the message.
        Transaction (ValidatorRegistryTransaction): The transaction the
            message is associated with.
    """
    MessageType = "/ledger.transaction.ValidatorRegistry/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(ValidatorRegistryTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = ValidatorRegistryTransaction(tinfo)


class Update(object):
    """Updates represent potential changes to the endpoint registry.

    Attributes:
        validator_registry.Update.KnownVerbs (list): A list of possible update
            actions. Currently register. In the future may include revoke.
        verb (str): The action of this update, defaults to 'reg'.
        validator_name (str): The name of the endpoint.
        validator_id (str): The identifier of the endpoint.
        poet_public_key: Public key used by this poet to sign wait certificates
        anti_sybil_id: A token, such as an EPID pseudonym, to restrict the
            number of identities an entity can assume in the network.
        signup_info: Serialized authorization data for network enrollment
            Contains required elements poet_public_key and anti_sybil_id
    """
    KnownVerbs = ['reg']

    @staticmethod
    def register_validator(validator_name, validator_id, signup_info):
        """Creates a new Update object to register a validator.

        Args:
            validator_name (str): Human readable name of the validator
            validator_id (str): Bitcoin-style address of the validator's
                public key
            signup_info (SignupInfo): A SignupInfo object that was
                previously created by a call to SignupInfo.create_signup_info

        Returns:
            validator_registry.Update: An update object for registering the
                validator's details.
        """
        minfo = {
            'validator_name': validator_name,
            'validator_id': validator_id,
            'signup_info': signup_info.serialize(),
            'verb': 'reg'
        }
        return Update(minfo)

    def __init__(self, minfo=None):
        """Constructor for Update class.

        Args:
            minfo (dict): Update values extracted from a message
                {'verb', 'validator_name', 'validator_id', 'signup_info'}
        """

        if minfo is None:
            minfo = {}
        self.verb = minfo.get('verb', 'reg')
        self.validator_name = minfo.get('validator_name', '')
        self.validator_id = minfo.get('validator_id', NullIdentifier)
        self.signup_info = \
            SignupInfo.signup_info_from_serialized(minfo.get('signup_info'))

    def __str__(self):
        return str(self.dump())

    def is_valid_name(self):
        """
        Ensure that the name property meets syntactic requirements.
        """

        if self.validator_name == '':
            return True

        if len(self.validator_name) >= 64:
            LOGGER.debug('invalid name %s; must be less than 64 bytes',
                         self.validator_name)
            return False

        return True

    def check_valid(self, store, txn):
        """Determines if the update is valid.
            Check policy on each element of validator_name, validator_id,
            and signup_info

        Args:
            store (Store): Transaction store.
            txn (Transaction): Transaction encompassing this update.
        """
        LOGGER.debug('check update %s from %s', str(self), self.validator_id)

        # Check name
        if not self.is_valid_name():
            raise InvalidTransactionError(
                'Illegal validator name {}'.format(self.validator_name[:64]))

        # Check registering validator matches transaction signer.
        if self.validator_id != txn.OriginatorID:
            raise InvalidTransactionError(
                'Signature mismatch on validator registration with validator'
                ' {} signed by {}'.format(self.validator_id,
                                          txn.OriginatorID))

        # Nothing to check for anti_sybil_id
        # Apply will invalidate any previous entries for this anti_sybil_id
        # and create a new entry.

        try:
            public_key_hash = \
                hashlib.sha256(
                    signing.encode_pubkey(
                        txn.originator_public_key,
                        'hex').encode()).hexdigest()

            self.signup_info.check_valid(
                originator_public_key_hash=public_key_hash,
                most_recent_wait_certificate_id='0' * 16)
        except ValueError as error:
            raise InvalidTransactionError(
                'Invalid Signup Info: {0}, Reason: {1}'.format(
                    self.signup_info,
                    error))

        return True

    def apply(self, store, txn, block):
        """Applies the update to the validator entry in the store.

        Args:
            store (Store): Transaction store.
            txn (Transaction): Transaction encompassing this update.
        """
        LOGGER.debug('apply %s', str(self))

        if self.verb == 'reg':
            # invalidate any previous entries
            try:
                registration = \
                    store.lookup(
                        'poet-validator:anti-sybil-id',
                        self.signup_info.anti_sybil_id)
                registration['revoked'] = txn.Identifier

                LOGGER.info(
                    'Transaction %s Revoking public key for %s (%s) '
                    'with anti-Sybil ID %s',
                    txn.Identifier,
                    self.validator_name,
                    self.validator_id,
                    self.signup_info.anti_sybil_id)
            except KeyError:
                pass

            # If we don't have a block, then we cannot get a block number
            # from it.  In that case, a default of zero is fine.

            store[self.validator_id] = {
                'object-type': 'poet-validator',
                'object-id': self.validator_id,
                'validator-id': self.validator_id,
                'validator-name': self.validator_name,
                'poet-public-key': self.signup_info.poet_public_key,
                'anti-sybil-id': self.signup_info.anti_sybil_id,
                'revoked': None,
                'updated-in-block-number': block.BlockNum if block else 0
            }
        else:
            LOGGER.info('unknown verb %s', self.verb)

    def dump(self):
        """Returns a dict with attributes from the update object.

        Returns:
            dict: A dictionary containing attributes from the update
                object.
        """

        result = {
            'verb': self.verb,
            'validator_name': self.validator_name,
            'validator_id': self.validator_id,
            'signup_info': self.signup_info.serialize(),
        }
        return result


class ValidatorRegistryTransaction(transaction.Transaction):
    """A Transaction is a set of updates to be applied atomically
    to a ledger.

    It has a unique identifier and a signature to validate the source.

    Attributes:
        ValidatorRegistryTransaction.TransactionTypeName (str): The name of the
            validator registry transaction type.
        ValidatorRegistryTransaction.TransactionStoreType (type): The type of
            the transaction store.
        ValidatorRegistryTransaction.MessageType (type): The object type of the
            message associated with this transaction.
        Updates (list): A list of validator registry updates associated
            with this transaction.
    """
    TransactionTypeName = '/ValidatorRegistryTransaction'
    TransactionStoreType = object_store.ObjectStore
    MessageType = ValidatorRegistryTransactionMessage

    @staticmethod
    def register_validator(validator_name, validator_id, signup_info):
        # pylint disable=invalid-name
        """Creates a new ValidatorRegistryTransaction object

        Args:
            validator_name (str): Human readable name of the validator
            validator_id (str): Bitcoin-style address of the validators
                public key
            signup_info (SignupInfo): A SignupInfo object that was
                previously created by a call to SignupInfo.create_signup_info
        Returns:
            validator_registry.Update: A transaction containing an update for
                registering the validator.
        """
        regtxn = ValidatorRegistryTransaction()
        regtxn.update = \
            Update.register_validator(
                validator_name,
                validator_id,
                signup_info)

        return regtxn

    @staticmethod
    def get_store(journal, block_id):
        """Retrieves the validator registry transaction store associated with
        the block referenced by the block ID provided.

        Args:
            journal: The journal object
            block_id: The ID of the block for which store is being requested

        Returns:
            The validator registry store at the block requested
        """
        return \
            journal.get_transaction_store(
                family=ValidatorRegistryTransaction,
                block_id=block_id)

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(ValidatorRegistryTransaction, self).__init__(minfo)

        self.update = None

        if 'Update' in minfo:
            self.update = Update(minfo=minfo['Update'])

    def __str__(self):
        return str(self.update)

    def check_valid(self, store):
        """Determines if the transaction is valid.

        Args:
            store (dict): Transaction store mapping.

        Returns:
            bool: Whether or not the transaction is valid.
        """
        super(ValidatorRegistryTransaction, self).check_valid(store)
        assert self.update
        self.update.check_valid(store, self)
        return True

    def apply(self, store):
        """Applies all the updates in the transaction to the endpoint
        in the transaction store.

        Args:
            store (dict): Transaction store mapping.
        """
        self.apply_with_block(store, None)

    def apply_with_block(self, store, block):
        """Applies all the updates in the transaction to the endpoint
        in the transaction store.

        Args:
            store (dict): Transaction store mapping.
            block: The containing block
        """
        self.update.apply(store, self, block)

    def dump(self):
        """Returns a dict with attributes from the transaction object.

        Returns:
            dict: The updates from the transaction object.
        """
        result = super(ValidatorRegistryTransaction, self).dump()

        result['Update'] = self.update.dump()

        return result

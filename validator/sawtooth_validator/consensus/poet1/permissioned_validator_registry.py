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


from journal import transaction
from journal import object_store
from journal.messages import transaction_message
from gossip.common import NullIdentifier
from sawtooth.exceptions import InvalidTransactionError

LOGGER = logging.getLogger(__name__)

# pylint: disable=invalid-name
PermissionedValidators = None


def set_global_permissioned_validators(permissioned_validators):
    # pylint: disable=global-statement
    global PermissionedValidators
    if not PermissionedValidators:
        PermissionedValidators = permissioned_validators
        LOGGER.info('PermissionedValidators: %s;',
                    PermissionedValidators)


def register_transaction_types(journal):
    """Registers the validator registry transaction types on the ledger.

    Args:
        ledger (journal.journal_core.Journal): The ledger to register
            the transaction type against.
    """
    journal.dispatcher.register_message_handler(
        PermissionedValidatorRegistryTransactionMessage,
        transaction_message.transaction_message_handler)
    journal.add_transaction_store(PermissionedValidatorRegistryTransaction)
    set_global_permissioned_validators(journal.permissioned_validators)


class PermissionedValidatorRegistryTransactionMessage(
        transaction_message.TransactionMessage):
    MessageType =\
        "/ledger.transaction.PermissionedValidatorRegistry/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(PermissionedValidatorRegistryTransactionMessage, self)\
            .__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = PermissionedValidatorRegistryTransaction(tinfo)


class Update(object):
    KnownVerbs = ['reg']

    def __init__(self, minfo=None):
        """Constructor for Update class.

        Args:
            minfo (dict): Update values extracted from a message
                {'verb', 'whitelist_name', 'permissioned-public-key'}
        """

        if minfo is None:
            minfo = {}
        self.verb = minfo.get('verb', 'reg')
        self.whitelist_name = minfo.get('whitelist_name', '')
        self.permissioned_public_keys = minfo.get('permissioned_public_keys',
                                                  NullIdentifier)
        self.permissioned_addrs = minfo.get('permissioned_addrs',
                                            NullIdentifier)

    def __str__(self):
        return str(self.dump())

    def is_valid_name(self):
        """
        Ensure that the name property meets syntactic requirements.
        """

        if self.whitelist_name == '':
            return True

        if len(self.whitelist_name) >= 64:
            LOGGER.debug('invalid name %s; must be less than 64 bytes',
                         self.whitelist_name)
            return False

        return True

    def check_valid(self, store, txn):
        """Determines if the update is valid.
            Check policy
        Args:
            store (Store): Transaction store.
            txn (Transaction): Transaction encompassing this update.
        """
        LOGGER.debug('check update %s from %s', str(self), self.whitelist_name)

        # Check name
        if not self.is_valid_name():
            raise InvalidTransactionError(
                'Illegal whitelist name {}'.format(self.whitelist_name[:64]))

#         try:
#             with open("/home/vagrant/sawtooth/whitelist.json")\
#                     as whitelist_fd:
#                 whitelist_dic = json.load(whitelist_fd)
#         except IOError, ex:
#             raise InvalidTransactionError(
#                 'could not open /home/vagrant/sawtooth/whitelist.json {}'
#                 .format(str(ex)))

        if not PermissionedValidators:
            raise InvalidTransactionError('No Permissioned Validators')

        whitelist_dic = PermissionedValidators
        if 'PermissionedValidatorPublicKeys' in whitelist_dic:
            permissioned_public_keys =\
                whitelist_dic['PermissionedValidatorPublicKeys']
            for public_key in self.permissioned_public_keys:
                if public_key not in permissioned_public_keys:
                    raise InvalidTransactionError(
                        'Illegal public key {}'
                        .format(str(public_key)))

        if 'PermissionedValidatorAddrs' in whitelist_dic:
            permissioned_addrs = whitelist_dic['PermissionedValidatorAddrs']
            for addr in self.permissioned_addrs:
                if addr not in permissioned_addrs:
                    raise InvalidTransactionError(
                        'Illegal public addr {}'
                        .format(str(addr)))

        return True

    def apply(self, store, txn):
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
                        'permissioned-validator:whitelist-name',
                        self.whitelist_name)
                registration['revoked'] = txn.Identifier

                LOGGER.info(
                    'Transaction %s Revoking for %s',
                    txn.Identifier,
                    self.whitelist_name)

            except KeyError:
                pass

            store[self.whitelist_name] = {
                'object-type': 'permissioned-validator',
                'object-id': self.whitelist_name,
                'whitelist-name': self.whitelist_name,
                'permissioned-public-keys': self.permissioned_public_keys,
                'permissioned-addrs': self.permissioned_addrs,
                'revoked': None
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
            'whitelist_name': self.whitelist_name,
            'permissioned_public_keys': self.permissioned_public_keys,
            'permissioned_addrs': self.permissioned_addrs
        }
        return result


class PermissionedValidatorRegistryTransaction(transaction.Transaction):
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
    TransactionTypeName = '/PermissionedValidatorRegistryTransaction'
    TransactionStoreType = object_store.ObjectStore
    MessageType = PermissionedValidatorRegistryTransactionMessage

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(PermissionedValidatorRegistryTransaction, self).__init__(minfo)

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
        super(PermissionedValidatorRegistryTransaction, self)\
            .check_valid(store)
        assert self.update
        self.update.check_valid(store, self)
        return True

    def apply(self, store):
        """Applies all the updates in the transaction to the endpoint
        in the transaction store.

        Args:
            store (dict): Transaction store mapping.
        """
        self.update.apply(store, self)

    def dump(self):
        """Returns a dict with attributes from the transaction object.

        Returns:
            dict: The updates from the transaction object.
        """
        result = super(PermissionedValidatorRegistryTransaction, self).dump()

        result['Update'] = self.update.dump()

        return result

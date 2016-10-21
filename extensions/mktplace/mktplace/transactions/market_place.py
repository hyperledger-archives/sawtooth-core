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

from mktplace.transactions import account_update
from mktplace.transactions import asset_type_update
from mktplace.transactions import asset_update
from mktplace.transactions import exchange_offer_update
from mktplace.transactions import exchange_update
from mktplace.transactions import holding_update
from mktplace.transactions import incentive_update
from mktplace.transactions import liability_update
from mktplace.transactions import participant_update
from mktplace.transactions import payment
from mktplace.transactions import sell_offer_update
from gossip import node, signed_object
from journal import transaction, transaction_block
from journal import object_store
from journal.messages import transaction_message

logger = logging.getLogger(__name__)

ValidatorHoldingID = None
BaseValidationReward = 100


def register_transaction_types(journal):
    journal.dispatcher.register_message_handler(
        MarketPlaceTransactionMessage,
        transaction_message.transaction_message_handler)
    journal.add_transaction_store(MarketPlaceTransaction)
    journal.on_block_test += _block_test
    journal.on_build_block += _build_block
    journal.on_claim_block += _claim_block
    journal.on_genesis_block += _prepare_genesis_transactions


def _build_block(journal, block):
    logger.debug('build a new block')

    global ValidatorHoldingID
    if not ValidatorHoldingID:
        mktstore = journal.global_store.TransactionStores.get(
            MarketPlaceTransaction.TransactionTypeName)
        if mktstore:
            holdingname = "//{0}/holding/validation-token".format(
                journal.local_node.Name)
            holdingid = mktstore.n2i(holdingname, 'Holding')
            if holdingid:
                logger.info('set validator holding id to %s', holdingid)
                ValidatorHoldingID = holdingid

    # the initial count is the minimum incentive for validating a block
    count = BaseValidationReward
    for txnid in block.TransactionIDs:
        txn = journal.transaction_store[txnid]
        if isinstance(txn, MarketPlaceTransaction):
            # check for payment, we don't actually need to
            # check whether the payment is valid at this point
            # just to make sure that the incentive transaction
            # is not greater than the total payments
            if txn.Payment:
                count += txn.Payment.Count

    # build the incentive transaction, sign it and add it to the
    # local store but dont send it out, use the local store as
    # a temporary holding place
    if ValidatorHoldingID:

        itxn = MarketPlaceTransaction(minfo={
            'Updates': [{
                'UpdateType': incentive_update.IncentiveUpdate.UpdateType,
                'HoldingId': ValidatorHoldingID,
                'Count': count,
            }]
        })
        itxn.sign_from_node(journal.local_node)

        logger.debug('add incentive transaction %s to block', itxn.Identifier)
        journal.transaction_store[itxn.Identifier] = itxn
        block.TransactionIDs.append(itxn.Identifier)


def _claim_block(journal, block):
    logger.info('prepare to claim block %s', block.Identifier)

    # send out the incentive transactions prior to sending out the
    # actual block
    itxns = []

    for txnid in block.TransactionIDs:
        txn = journal.transaction_store[txnid]
        if isinstance(txn, MarketPlaceTransaction):
            # grab all of the incentive transactions, in theory one
            # should be sufficient though i suppose more could be added
            # to redirect funds to multiple locations...
            update = txn.get_first_update()
            if update.UpdateType == \
                    incentive_update.IncentiveUpdate.UpdateType:
                itxns.append(txn)

    logger.debug('found %s incentive transactions while claiming block %s',
                 len(itxns), block.Identifier)

    for itxn in itxns:
        itxn.Status = transaction.Status.pending
        msg = MarketPlaceTransactionMessage()
        msg.Transaction = itxn
        journal.gossip.broadcast_message(msg)

        logger.info(
            'sending the incentive transaction %s for holding %s for block %s',
            itxn.Identifier, itxn.get_first_update().HoldingID,
            block.Identifier)
        journal.gossip.broadcast_message(msg)


def _block_test(journal, block):
    logger.debug('test for valid marketplace block')
    assert block.Status == transaction_block.Status.complete

    # the initial count is the minimum incentive for validating a block
    count = BaseValidationReward
    itxns = []

    for txnid in block.TransactionIDs:
        txn = journal.transaction_store[txnid]
        if isinstance(txn, MarketPlaceTransaction):
            # grab all of the incentive transactions, in theory one
            # should be sufficient though i suppose more could be added
            # to redirect funds to multiple locations...
            update = txn.get_first_update()
            if update.UpdateType == \
                    incentive_update.IncentiveUpdate.UpdateType:
                itxns.append(txn)

            # check for payment, we don't actually need to
            # check whether the payment is valid at this point
            # just to make sure that the incentive transaction
            # is not greater than the total payments
            elif txn.Payment:
                count += txn.Payment.Count

    # now make sure that the incentive transactions do not over claim resources
    for itxn in itxns:
        if itxn.OriginatorID != block.OriginatorID:
            logger.warn(
                'participant %s attempted to claim incentive on block %s '
                'committed by %s',
                itxn.OriginatorID, block.Identifier, block.OriginatorID)
            return False

        count -= itxn.Update.Count

    logger.debug('block payment is %s', count)
    return 0 <= count


def _prepare_genesis_transactions(journal):
    logger.debug('prepare marketplace transactions for genesis block')

    # Set up a random key for generating the genesis objects, we
    # "trust" that the key is not kept. At some point this should be
    # revisited, suggestions about "burning" the private key
    signingkey = signed_object.generate_signing_key()
    identifier = signed_object.generate_identifier(signingkey)
    signnode = node.Node(identifier=identifier, signingkey=signingkey)

    # Create a participant for the global market
    txn = MarketPlaceTransaction(minfo={
        'Updates': [
            {
                'UpdateType': participant_update.Register.UpdateType,
                'Name': 'marketplace',
                'Description': 'The ROOT participant for the marketplace',
            }
        ]
    })
    txn.sign_from_node(signnode)
    journal.add_pending_transaction(txn)
    logger.info('Created market participant: %s', txn.Identifier)
    lasttxn = txn.Identifier
    mktid = txn.Identifier

    # Create an asset type for participants
    txn = MarketPlaceTransaction(minfo={
        'Updates': [
            {
                'UpdateType': asset_type_update.Register.UpdateType,
                'CreatorId': mktid,
                'Restricted': False,
                'Name': '/asset-type/participant',
                'Description': 'Canonical type for participant assets'
            }
        ]
    })
    txn.Dependencies = [lasttxn]
    txn.sign_from_node(signnode)

    journal.add_pending_transaction(txn)
    logger.info('Created participant asset type: %s', txn.Identifier)
    lasttxn = txn.Identifier

    # Create an asset type for random tokens
    txn = MarketPlaceTransaction(minfo={
        'Updates': [
            {
                'UpdateType': asset_type_update.Register.UpdateType,
                'CreatorId': mktid,
                'Restricted': True,
                'Name': '/asset-type/token',
                'Description': 'Canonical type for meaningless tokens that '
                               'are useful for bootstrapping'
            }
        ]
    })
    txn.Dependencies = [lasttxn]
    txn.sign_from_node(signnode)

    journal.add_pending_transaction(txn)
    logger.info('Created token asset type: %s', txn.Identifier)
    lasttxn = txn.Identifier
    assettypeid = txn.Identifier

    # Create an asset for the tokens
    txn = MarketPlaceTransaction(minfo={
        'Updates': [
            {
                'UpdateType': asset_update.Register.UpdateType,
                'CreatorId': mktid,
                'AssetTypeId': assettypeid,
                'Restricted': False,
                'Consumable': False,
                'Divisible': False,
                'Name': '/asset/token',
                'Description': 'Canonical asset for tokens'
            }
        ]
    })
    txn.Dependencies = [lasttxn]
    txn.sign_from_node(signnode)

    journal.add_pending_transaction(txn)
    logger.info('Created token asset: %s', txn.Identifier)

    # Create an asset for the validation tokens
    txn = MarketPlaceTransaction(minfo={
        'Updates': [{
            'UpdateType': asset_update.Register.UpdateType,
            'CreatorId': mktid,
            'AssetTypeId': assettypeid,
            'Restricted': True,
            'Consumable': True,
            'Divisible': False,
            'Name': '/asset/validation-token',
            'Description': 'Canonical asset for validation tokens'
        }]}
    )

    txn.Dependencies = [lasttxn]
    txn.sign_from_node(signnode)

    journal.add_pending_transaction(txn)
    logger.info('Created validation token asset: %s', txn.Identifier)


class MarketPlaceGlobalStore(object_store.ObjectStore):
    def __init__(self, prevstore=None, storeinfo=None, readonly=False):
        super(MarketPlaceGlobalStore, self).__init__(prevstore, storeinfo,
                                                     readonly)

    def clone_store(self, storeinfo=None, readonly=False):
        """
        Create a new checkpoint that can be modified

        :return: a new checkpoint that extends the current store
        :rtype: KeyValueStore
        """
        return MarketPlaceGlobalStore(self, storeinfo, readonly)

    def i2n(self, objectid, objinfo=None):
        """
        Convert an objectid into a canonical name representation
        """

        try:
            if objinfo is None:
                objinfo = self.get(objectid)
        except KeyError:
            return None

        name = objinfo.get('name')

        if not name:
            return '///{0}'.format(objectid)

        if objinfo.get('object-type') == \
                participant_update.ParticipantObject.ObjectTypeName:
            return '//{0}'.format(name)

        creatorid = objinfo.get('creator')
        assert creatorid

        return '{0}{1}'.format(self.i2n(creatorid), name)

    def n2i(self, name, obj_type):
        """
        Find an object by name

        Args:
            obj_type: The object-type, Asset, Participant...
        """

        if name.startswith('///'):
            id = name.replace('///', '', 1)
            return id if id in self else None
        if name.startswith('//'):
            def unpack_indeterminate(creator, *path):
                return creator, path

            creator, path = unpack_indeterminate(*name[2:].split('/'))
            try:
                creator_id = self.lookup("Participant:full-name",
                                         "//" + creator)['object-id']
            except KeyError:
                return None
            if path:
                name = '{}/{}'.format(creator_id, "/".join(path))
            else:
                name = "//" + creator
        ident = None
        index = obj_type + ":full-name"
        try:
            ident = self.lookup(index, name)['object-id']
        except KeyError:
            pass
        return ident


class MarketPlaceTransactionMessage(transaction_message.TransactionMessage):
    MessageType = "/mktplace.transactions.MarketPlace/Transaction"

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}
        super(MarketPlaceTransactionMessage, self).__init__(minfo=minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = MarketPlaceTransaction(tinfo)


class MarketPlaceTransaction(transaction.UpdatesTransaction):
    """
    A Transaction is a set of updates to be applied atomically to a journal. It
    has a unique identifier and a signature to validate the source.
    """

    TransactionTypeName = '/MarketPlaceTransaction'
    TransactionStoreType = MarketPlaceGlobalStore
    MessageType = MarketPlaceTransactionMessage

    UpdateRegistry = {
        account_update.Register.UpdateType: account_update.Register,
        account_update.Unregister.UpdateType: account_update.Unregister,
        account_update.UpdateDescription.UpdateType:
            account_update.UpdateDescription,
        account_update.UpdateName.UpdateType: account_update.UpdateName,

        asset_update.Register.UpdateType: asset_update.Register,
        asset_update.Unregister.UpdateType: asset_update.Unregister,
        asset_update.UpdateDescription.UpdateType:
            asset_update.UpdateDescription,
        asset_update.UpdateName.UpdateType: asset_update.UpdateName,

        asset_type_update.Register.UpdateType: asset_type_update.Register,
        asset_type_update.Unregister.UpdateType: asset_type_update.Unregister,
        asset_type_update.UpdateDescription.UpdateType:
            asset_type_update.UpdateDescription,
        asset_type_update.UpdateName.UpdateType: asset_type_update.UpdateName,

        exchange_offer_update.Register.UpdateType:
            exchange_offer_update.Register,
        exchange_offer_update.Unregister.UpdateType:
            exchange_offer_update.Unregister,
        exchange_offer_update.UpdateDescription.UpdateType:
            exchange_offer_update.UpdateDescription,
        exchange_offer_update.UpdateName.UpdateType:
            exchange_offer_update.UpdateName,


        holding_update.Register.UpdateType: holding_update.Register,
        holding_update.Unregister.UpdateType: holding_update.Unregister,
        holding_update.UpdateDescription.UpdateType:
            holding_update.UpdateDescription,
        holding_update.UpdateName.UpdateType: holding_update.UpdateName,

        liability_update.Register.UpdateType: liability_update.Register,
        liability_update.Unregister.UpdateType: liability_update.Unregister,
        liability_update.UpdateDescription.UpdateType:
            liability_update.UpdateDescription,
        liability_update.UpdateName.UpdateType: liability_update.UpdateName,

        participant_update.Register.UpdateType: participant_update.Register,
        participant_update.Unregister.UpdateType:
            participant_update.Unregister,
        participant_update.UpdateDescription.UpdateType:
            participant_update.UpdateDescription,
        participant_update.UpdateName.UpdateType:
            participant_update.UpdateName,

        sell_offer_update.Register.UpdateType: sell_offer_update.Register,
        sell_offer_update.Unregister.UpdateType: sell_offer_update.Unregister,
        sell_offer_update.UpdateDescription.UpdateType:
            sell_offer_update.UpdateDescription,
        sell_offer_update.UpdateName.UpdateType: sell_offer_update.UpdateName,

        exchange_update.Exchange.UpdateType: exchange_update.Exchange,
        incentive_update.IncentiveUpdate.UpdateType:
            incentive_update.IncentiveUpdate
    }

    PaymentRegistry = {
        payment.PayFromHolding.PaymentType: payment.PayFromHolding
    }

    def __init__(self, minfo=None):
        if minfo is None:
            minfo = {}

        self.Payment = None

        if 'Payment' in minfo:
            pinfo = minfo['Payment']
            ptype = pinfo.get('PaymentType')
            if not ptype or ptype not in self.PaymentRegistry:
                logger.warn(
                    'transaction contains invalid payment type, skipping')
            else:
                self.Payment = self.PaymentRegistry[ptype](self, pinfo)
        super(MarketPlaceTransaction, self).__init__(minfo=minfo)

    def check_valid(self, store):

        # check the payment
        if self.Payment and not self.Payment.is_valid(store):
            logger.debug('invalid payment: %s', str(self.Payment))
            return False

        return super(MarketPlaceTransaction, self).check_valid(store)

    def add_to_pending(self):
        """
        Predicate to note that a transaction should be added to pending
        transactions. In general incentive transactions should not be
        including in the pending transaction list.
        """
        if self.get_first_update().UpdateType != \
                incentive_update.IncentiveUpdate.UpdateType:
            return True

        return False

    def get_updates(self):
        return self._updates

    def get_first_update(self):
        if len(self._updates) == 0:
            return None
        return self._updates[0]

    def register_updates(self, registry):
        for update_type, update in self.UpdateRegistry.iteritems():
            registry.register(update_type, update)

    def dump(self):
        result = super(MarketPlaceTransaction, self).dump()
        if self.Payment:
            result['Payment'] = self.Payment.dump()
        dependencies = result.get('Dependencies', [])
        for refid in self.get_first_update().References:
            if refid not in dependencies:
                dependencies.append(refid)
        result['Dependencies'] = dependencies
        return result

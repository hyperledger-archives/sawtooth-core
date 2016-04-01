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
from journal import transaction, transaction_block, global_store_manager
from journal.messages import transaction_message

logger = logging.getLogger(__name__)

ValidatorHoldingID = None
BaseValidationReward = 100


def register_transaction_types(journal):
    journal.register_message_handler(
        MarketPlaceTransactionMessage,
        transaction_message.transaction_message_handler)
    journal.add_transaction_store(MarketPlaceTransaction)
    journal.onBlockTest += _block_test
    journal.onBuildBlock += _build_block
    journal.onClaimBlock += _claim_block
    journal.onGenesisBlock += _prepare_genesis_transactions


def _build_block(ledger, block):
    logger.debug('build a new block')

    global ValidatorHoldingID
    if not ValidatorHoldingID:
        mktstore = ledger.GlobalStore.TransactionStores.get(
            MarketPlaceTransaction.TransactionTypeName)
        if mktstore:
            holdingname = "//{0}/holding/validation-token".format(
                ledger.LocalNode.Name)
            holdingid = mktstore.n2i(holdingname)
            if holdingid:
                logger.info('set validator holding id to %s', holdingid)
                ValidatorHoldingID = holdingid

    # the initial count is the minimum incentive for validating a block
    count = BaseValidationReward
    for txnid in block.TransactionIDs:
        txn = ledger.TransactionStore[txnid]
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
        itxn = MarketPlaceTransaction()
        itxn.Update = incentive_update.IncentiveUpdate()
        itxn.Update.HoldingID = ValidatorHoldingID
        itxn.Update.Count = count
        itxn.sign_from_node(ledger.LocalNode)

        logger.debug('add incentive transaction %s to block', itxn.Identifier)
        ledger.TransactionStore[itxn.Identifier] = itxn
        block.TransactionIDs.append(itxn.Identifier)


def _claim_block(ledger, block):
    logger.info('prepare to claim block %s', block.Identifier)

    # send out the incentive transactions prior to sending out the
    # actual block
    itxns = []

    for txnid in block.TransactionIDs:
        txn = ledger.TransactionStore[txnid]
        if isinstance(txn, MarketPlaceTransaction):
            # grab all of the incentive transactions, in theory one
            # should be sufficient though i suppose more could be added
            # to redirect funds to multiple locations...
            if txn.Update.UpdateType == \
                    incentive_update.IncentiveUpdate.UpdateType:
                itxns.append(txn)

    logger.debug('found %s incentive transactions while claiming block %s',
                 len(itxns), block.Identifier)

    for itxn in itxns:
        itxn.Status = transaction.Status.pending
        msg = MarketPlaceTransactionMessage()
        msg.Transaction = itxn
        msg.SenderID = ledger.LocalNode.Identifier
        msg.sign_from_node(ledger.LocalNode)

        logger.info(
            'sending the incentive transaction %s for holding %s for block %s',
            itxn.Identifier, itxn.Update.HoldingID, block.Identifier)
        ledger.handle_message(msg)


def _block_test(ledger, block):
    logger.debug('test for valid marketplace block')
    assert block.Status == transaction_block.Status.complete

    # the initial count is the minimum incentive for validating a block
    count = BaseValidationReward
    itxns = []

    for txnid in block.TransactionIDs:
        txn = ledger.TransactionStore[txnid]
        if isinstance(txn, MarketPlaceTransaction):
            # grab all of the incentive transactions, in theory one
            # should be sufficient though i suppose more could be added
            # to redirect funds to multiple locations...
            if txn.Update.UpdateType == \
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
    txn = MarketPlaceTransaction()
    update = participant_update.Register(txn)
    update.Name = 'marketplace'
    update.Description = 'The ROOT participant for the marketplace'

    txn.Update = update

    txn.sign_from_node(signnode)
    journal.add_pending_transaction(txn)
    logger.info('Created market participant: %s', txn.Identifier)
    lasttxn = txn.Identifier

    mktid = update.ObjectID

    # Create an asset type for participants
    txn = MarketPlaceTransaction()
    update = asset_type_update.Register(txn)

    update.CreatorID = mktid

    # anyone can create participant assets for themselves
    update.Restricted = False

    update.Name = '/asset-type/participant'
    update.Description = 'Canonical type for participant assets'

    txn.Update = update
    txn.Dependencies = [lasttxn]
    txn.sign_from_node(signnode)

    journal.add_pending_transaction(txn)
    logger.info('Created participant asset type: %s', txn.Identifier)
    lasttxn = txn.Identifier

    assettypeid = update.ObjectID

    # Create an asset type for random tokens
    txn = MarketPlaceTransaction()
    update = asset_type_update.Register(txn)

    update.CreatorID = mktid
    update.Restricted = True  # there is only one asset based on the token type
    update.Name = '/asset-type/token'
    update.Description = 'Canonical type for meaningless tokens that are ' \
                         'very useful for bootstrapping'

    txn.Update = update
    txn.Dependencies = [lasttxn]
    txn.sign_from_node(signnode)

    journal.add_pending_transaction(txn)
    logger.info('Created token asset type: %s', txn.Identifier)
    lasttxn = txn.Identifier

    assettypeid = update.ObjectID

    # Create an asset for the tokens
    txn = MarketPlaceTransaction()
    update = asset_update.Register(txn)

    update.CreatorID = mktid
    update.AssetTypeID = assettypeid

    # anyone can create holdings with token instances
    update.Restricted = False

    # and these are infinitely replaceable
    update.Consumable = False

    update.Divisible = False
    update.Name = '/asset/token'
    update.Description = 'Canonical asset for tokens'

    txn.Update = update
    txn.Dependencies = [lasttxn]
    txn.sign_from_node(signnode)

    journal.add_pending_transaction(txn)
    logger.info('Created token asset: %s', txn.Identifier)

    # Create an asset for the validation tokens
    txn = MarketPlaceTransaction()
    update = asset_update.Register(txn)

    update.CreatorID = mktid
    update.AssetTypeID = assettypeid
    update.Restricted = True  # these assets are only created by the market
    update.Consumable = True
    update.Divisible = False
    update.Name = '/asset/validation-token'
    update.Description = 'Canonical asset for validation tokens'

    txn.Update = update
    txn.Dependencies = [lasttxn]
    txn.sign_from_node(signnode)

    journal.add_pending_transaction(txn)
    logger.info('Created validation token asset: %s', txn.Identifier)


class MarketPlaceGlobalStore(global_store_manager.KeyValueStore):
    def __init__(self, prevstore=None, storeinfo=None, readonly=False):
        super(MarketPlaceGlobalStore, self).__init__(prevstore, storeinfo,
                                                     readonly)

        self._namemapinitialized = False
        self._namemap = {}

    def clone_store(self, storeinfo=None, readonly=False):
        """
        Create a new checkpoint that can be modified

        :return: a new checkpoint that extends the current store
        :rtype: KeyValueStore
        """
        return MarketPlaceGlobalStore(self, storeinfo, readonly)

    def _initnamemap(self):
        """
        Initialize the name map, this is probably a bad thing to have
        around given that it is likely to end up in the shelve database
        for the global store. Oh well...
        """
        info = self.compose(readonly=True)
        for objid, objinfo in info.iteritems():
            name = self.i2n(objid)
            if not name.startswith('///'):
                self._namemap[name] = objid

        self._namemapinitialized = True

    def bind(self, fqname, objectid):
        """
        """
        self._namemap[fqname] = objectid

    def unbind(self, fqname):
        """
        """
        del self._namemap[fqname]

    def i2n(self, objectid):
        """
        Convert an objectid into a canonical name representation
        """

        try:
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

    def n2i(self, name):
        """
        Find an object by name
        """

        if name.startswith('///'):
            id = name.replace('///', '', 1)
            return id if id in self else None

        if not self._namemapinitialized:
            self._initnamemap()

        return self._namemap.get(name)


class MarketPlaceTransactionMessage(transaction_message.TransactionMessage):
    MessageType = "/" + __name__ + "/Transaction"

    def __init__(self, minfo={}):
        super(MarketPlaceTransactionMessage, self).__init__(minfo)

        tinfo = minfo.get('Transaction', {})
        self.Transaction = MarketPlaceTransaction(tinfo)


class MarketPlaceTransaction(transaction.Transaction):
    """
    A Transaction is a set of updates to be applied atomically to a journal. It
    has a unique identifier and a signature to validate the source.
    """

    TransactionTypeName = '/MarketPlaceTransaction'
    TransactionStoreType = MarketPlaceGlobalStore
    MessageType = MarketPlaceTransactionMessage

    UpdateRegistry = {
        asset_update.Register.UpdateType: asset_update.Register,
        asset_update.Unregister.UpdateType: asset_update.Unregister,
        asset_type_update.Register.UpdateType: asset_type_update.Register,
        asset_type_update.Unregister.UpdateType: asset_type_update.Unregister,
        exchange_offer_update.Register.UpdateType:
            exchange_offer_update.Register,
        exchange_offer_update.Unregister.UpdateType:
            exchange_offer_update.Unregister,
        holding_update.Register.UpdateType: holding_update.Register,
        holding_update.Unregister.UpdateType: holding_update.Unregister,
        liability_update.Register.UpdateType: liability_update.Register,
        liability_update.Unregister.UpdateType: liability_update.Unregister,
        participant_update.Register.UpdateType: participant_update.Register,
        participant_update.Unregister.UpdateType:
            participant_update.Unregister,
        sell_offer_update.Register.UpdateType: sell_offer_update.Register,
        sell_offer_update.Unregister.UpdateType: sell_offer_update.Unregister,
        account_update.Register.UpdateType: account_update.Register,
        account_update.Unregister.UpdateType: account_update.Unregister,
        exchange_update.Exchange.UpdateType: exchange_update.Exchange,
        incentive_update.IncentiveUpdate.UpdateType:
            incentive_update.IncentiveUpdate
    }

    PaymentRegistry = {
        payment.PayFromHolding.PaymentType: payment.PayFromHolding
    }

    def __init__(self, minfo={}):
        super(MarketPlaceTransaction, self).__init__(minfo)

        self.Update = None
        self.Payment = None

        if 'Update' in minfo:
            uinfo = minfo['Update']
            updatetype = uinfo.get('UpdateType')
            if not updatetype or updatetype not in self.UpdateRegistry:
                logger.warn(
                    'transaction contains an invalid update type, skipping')
            else:
                self.Update = self.UpdateRegistry[updatetype](self, uinfo)

        if 'Payment' in minfo:
            pinfo = minfo['Payment']
            ptype = pinfo.get('PaymentType')
            if not ptype or ptype not in self.PaymentRegistry:
                logger.warn(
                    'transaction contains invalid payment type, skipping')
            else:
                self.Payment = self.PaymentRegistry[ptype](self, pinfo)

    def __str__(self):
        return str(self.Update)

    def is_valid(self, store):
        if not super(MarketPlaceTransaction, self).is_valid(store):
            return False

        # this verifies that each update is correct independently
        # we also need to add a check that verifies that the overall
        # transaction is correct
        if not self.Update.is_valid(store):
            logger.debug('invalid transaction: %s', str(self.Update))
            return False

        # check the payment
        if self.Payment and not self.Payment.is_valid(store):
            logger.debug('invalid payment: %s', str(self.Payment))
            return False

        return True

    def add_to_pending(self):
        """
        Predicate to note that a transaction should be added to pending
        transactions. In general incentive transactions should not be
        including in the pending transaction list.
        """
        if self.Update.UpdateType != \
                incentive_update.IncentiveUpdate.UpdateType:
            return True

        return False

    def apply(self, store):
        """
        apply -- apply the transaction to the store
        """
        self.Update.apply(store)

        if self.Payment:
            self.Payment.apply(store)

    def dump(self):
        result = super(MarketPlaceTransaction, self).dump()

        result['Update'] = self.Update.dump()
        if self.Payment:
            result['Payment'] = self.Payment.dump()

        return result

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

from sawtooth.exceptions import InvalidTransactionError

from journal.transaction import Update
from mktplace.transactions import asset_type_update
from mktplace.transactions import asset_update
from mktplace.transactions import exchange_offer_update
from mktplace.transactions import holding_update
from mktplace.transactions import liability_update
from mktplace.transactions import market_place_object_update
from mktplace.transactions import participant_update
from mktplace.transactions import sell_offer_update


logger = logging.getLogger(__name__)


class _LiabilityInformation(object):
    @classmethod
    def load_from_store(cls, store, objectid):
        """
        Return a tuple with information about the holding or liability
        identified by objectid
        """

        types = [holding_update.HoldingObject.ObjectTypeName,
                 liability_update.LiabilityObject.ObjectTypeName]
        obj = market_place_object_update.MarketPlaceObject.get_valid_object(
            store, objectid, types)

        creatorid = obj.get('creator')
        count = obj.get('count')
        otype = obj.get('object-type')
        if otype == holding_update.HoldingObject.ObjectTypeName:
            asset = asset_update.AssetObject.load_from_store(store,
                                                             obj.get('asset'))
            assettype = asset_type_update.AssetTypeObject.load_from_store(
                store, asset.AssetTypeID)
        elif otype == liability_update.LiabilityObject.ObjectTypeName:
            asset = None
            assettype = asset_type_update.AssetTypeObject.load_from_store(
                store, obj.get('asset-type'))

        return cls(objectid, creatorid, otype, asset, assettype, count)

    def __init__(self, objectid, creatorid, otype, asset, assettype, count):
        # this is not going to work for liabilities yet so just fail early
        assert otype == holding_update.HoldingObject.ObjectTypeName

        self.ObjectID = objectid
        self.CreatorID = creatorid
        self.ObjectTypeName = otype
        self.Asset = asset
        self.AssetID = self.Asset.ObjectID if self.Asset else None
        self.AssetType = assettype
        self.AssetTypeID = self.AssetType.ObjectID
        self.Count = count

    def test_count(self, store, change):
        """
        Test the current asset/asset type count to see if the transfer can
        succeed. This is a simple check for now, but needs to accommodate
        non-consumable assets later.
        """

        # an asset that is consumable must be replaced if it is moved from
        # one holding to another
        if self.Asset and self.Asset.Consumable:
            return change <= self.Count

        # an asset that is not consumable can be moved so long as there is
        # at least one instance in the holding
        return 0 < self.Count

    def inc_count(self, store, change):
        obj = market_place_object_update.MarketPlaceObject.get_valid_object(
            store, self.ObjectID, self.ObjectTypeName)

        # we manage the counts for consumable assets, for non-consumable
        # assets we simply indicate that we have at least one copy of the
        # asset (which can be reproduced at need)
        if self.Asset.Consumable:
            obj['count'] = int(obj['count']) + int(change)
            store[self.ObjectID] = obj
        else:
            obj['count'] = 1
            store[self.ObjectID] = obj

    def dec_count(self, store, change):
        obj = market_place_object_update.MarketPlaceObject.get_valid_object(
            store, self.ObjectID, self.ObjectTypeName)

        # if the asset is consumable then we need to manage the counts
        # explicitly for non-consumable assets the count is never decremented,
        # once an asset is in a holding it is there forever
        if self.Asset.Consumable:
            obj['count'] = int(obj['count']) - int(change)

            # there are at least a couple cases where this might actually
            # happen and we should find another way to test... for example,
            # circular or multiple withdrawals from a holding/liability within
            # a single transaction
            assert 0 <= obj['count']

            store[self.ObjectID] = obj


class _OfferInformation(object):
    @classmethod
    def load_from_store(cls, store, offerid):
        """
        Return a tuple with information about the sell or exchange offer
        identified by offerid
        """

        types = [exchange_offer_update.ExchangeOfferObject.ObjectTypeName,
                 sell_offer_update.SellOfferObject.ObjectTypeName]
        obj = market_place_object_update.MarketPlaceObject.get_valid_object(
            store, offerid, types)

        otype = obj.get('object-type')
        iinfo = _LiabilityInformation.load_from_store(store, obj.get('input'))
        oinfo = _LiabilityInformation.load_from_store(store, obj.get('output'))
        ratio = float(obj.get('ratio'))
        minimum = int(obj.get('minimum'))
        maximum = int(obj.get('maximum'))
        execution = obj.get('execution')
        estate = obj.get('execution-state')

        return cls(offerid, otype, iinfo, oinfo, ratio, minimum, maximum,
                   execution, estate)

    def __init__(self, objectid, otype, iinfo, oinfo, ratio, minimum, maximum,
                 execution, estate):
        self.ObjectID = objectid
        self.ObjectTypeName = otype
        self.PayeeInfo = iinfo
        self.PayerInfo = oinfo
        self.Ratio = float(ratio)
        self.Minimum = minimum
        self.Maximum = maximum
        self.Execution = execution
        self.ExecutionState = estate

    def record_participant(self, store, payer):
        """
        Record the ID of the payer of the transaction in order to ensure that
        the transaction executes at most one time. Called as a trigger.

        Args:
            store -- current cached state
            payer -- liability info for the source of assets being fed into
                this offer
        """
        if payer.CreatorID not in self.ExecutionState['ParticipantList']:
            self.ExecutionState['ParticipantList'].append(payer.CreatorID)

            types = [exchange_offer_update.ExchangeOfferObject.ObjectTypeName,
                     sell_offer_update.SellOfferObject.ObjectTypeName]
            obj = \
                market_place_object_update.MarketPlaceObject.get_valid_object(
                    store, self.ObjectID, types)
            obj['execution-state'] = self.ExecutionState

            store[self.ObjectID] = obj

    def drop_offer(self, store):
        """
        Remove the offer from the database, called as a trigger when the offer
        execution method is 'ExecuteOnce'

        Args:
            store -- current cached state
        """
        del store[self.ObjectID]

    def triggers(self, count, payer):
        if self.Execution == 'ExecuteOnce':
            return [lambda store: self.drop_offer(store)]

        elif self.Execution == 'ExecuteOncePerParticipant':
            return [lambda store: self.record_participant(store, payer)]

        return []

    def test_offer(self, count, payer):
        """
        Apply offer specific conditions to the transaction.

        Args:
            count -- the number of assets being fed into the offer
            payer -- liability info for the source of assets being fed into
                this offer
        """

        # First Test: we can only move holdings to holdings and liabilities to
        # liabilities
        if payer.ObjectTypeName != self.PayeeInfo.ObjectTypeName:
            logger.info('mismatch in holding types; %s != %s',
                        payer.ObjectTypeName, self.PayeeInfo.ObjectTypeName)
            return False

        # Second Test: if we are moving between holdings then the assets must
        # match
        if self.PayeeInfo.ObjectTypeName == \
                holding_update.HoldingObject.ObjectTypeName:
            if payer.AssetID != self.PayeeInfo.AssetID:
                logger.info('mismatch in asset identifiers; %s != %s',
                            payer.AssetID, self.PayeeInfo.AssetID)
                return False

        # Third Test: if we are moving between liabilities then the asset types
        # must match
        if self.PayeeInfo.ObjectTypeName == \
                liability_update.LiabilityObject.ObjectTypeName:
            if payer.AssetTypeID != self.PayeeInfo.AssetTypeID:
                logger.info('mismatch in asset type identifiers; %s != %s',
                            payer.AssetID, self.PayeeInfo.AssetID)
                return False

        # Fourth Test: If a minimum or maximum count has been set, then we must
        # respect it
        if count < self.Minimum or self.Maximum < count:
            logger.info('count too big or too small; %d <= %d <= %d',
                        self.Minimum, count, self.Maximum)
            return False

        # Fifth Test: If the ExecuteOncePerParticipant modifier has been set,
        # then make sure that this particular participant has not executed this
        # offer in the past
        if self.Execution == 'ExecuteOncePerParticipant':
            if payer.CreatorID in self.ExecutionState['ParticipantList']:
                logger.info('attempt to double spend offer %s by %s',
                            self.ObjectID, payer.CreatorID)
                return False

        return True


class _Adjustment(object):
    def __init__(self, oinfo, iinfo, count, triggers):
        """
        Create an Adjustment object from liability information for payer
        (input) and payee (output)
        """
        self.PayerInfo = oinfo
        self.PayeeInfo = iinfo
        self.Count = count
        self.Triggers = triggers[:]

    def apply(self, store):
        logger.debug('apply adjustment, %s, %s, %d', self.PayerInfo.ObjectID,
                     self.PayeeInfo.ObjectID, self.Count)
        self.PayerInfo.dec_count(store, self.Count)
        self.PayeeInfo.inc_count(store, self.Count)
        for trigger in self.Triggers:
            trigger(store)


class Exchange(Update):
    UpdateType = 'Exchange'
    CreatorType = participant_update.ParticipantObject

    def __init__(self,
                 update_type,
                 initial_liability_id,
                 final_liability_id,
                 offer_id_list,
                 initial_count):

        super(Exchange, self).__init__(update_type)

        self._initial_liability_id = initial_liability_id
        self._final_liability_id = final_liability_id
        self._offer_id_list = offer_id_list
        self._initial_count = initial_count
        self.adjustment_list = None

    @property
    def References(self):
        return [self._initial_liability_id, self._final_liability_id] \
            + self._offer_id_list

    def build_adjustment_list(self, store):
        """
        Build a list of adjustments that will be applied to the ledger as a
        result of this update
        """

        self.adjustment_list = None

        # Create the initial source of assets
        payer = _LiabilityInformation.load_from_store(
            store,
            self._initial_liability_id
        )
        count = int(self._initial_count)
        if count <= 0:
            logger.debug('count of objects transferred goes to 0')
            return False

        if not payer.test_count(store, count):
            logger.info('insufficient initial funds in %s, %s of %s',
                        payer.ObjectID, payer.Count, count)
            return False

        adjustments = []
        for offerid in self._offer_id_list:

            offer = _OfferInformation.load_from_store(store, offerid)
            if not offer.test_offer(count, payer):
                return False

            logger.debug(
                'add adjustment from offer %s based on ratio %s, current '
                'count is %s',
                offer.ObjectID, offer.Ratio, count)
            adjustments.append(_Adjustment(payer, offer.PayeeInfo, count,
                                           offer.triggers(count, payer)))

            payer = offer.PayerInfo
            count = int(count * offer.Ratio)
            if count <= 0:
                logger.debug('count of objects transferred goes to 0')
                return False

            if not payer.test_count(store, count):
                logger.info('insufficient funds for offer %s, %s of %s',
                            payer.ObjectID, payer.Count, count)
                return False

        # Create the final destination for all of the transfers
        payee = _LiabilityInformation.load_from_store(store,
                                                      self._final_liability_id)
        adjustments.append(_Adjustment(payer, payee, count, []))

        self.adjustment_list = adjustments
        return True

    def check_valid(self, store, txn):
        logger.debug('market update: %s', str(self))

        # check to make sure that the originator has permission to decrement
        # the InitialLiability
        if not liability_update.LiabilityObject.is_valid_object(
                store, self._initial_liability_id):
            raise InvalidTransactionError(
                "Initial Liability does not reference a liability")

        # verify that the originator of the transaction is the owner of the
        # source liability
        payer = _LiabilityInformation.load_from_store(
            store,
            self._initial_liability_id
        )
        if not self.CreatorType.is_valid_creator(store, payer.CreatorID,
                                                 txn.OriginatorID):
            logger.warn(
                '%s does not have permission to transfer assets from '
                'liability %s',
                payer.CreatorID, self._initial_liability_id)
            raise InvalidTransactionError("Payer is not a valid Creator "
                                          "or does not have access to "
                                          "liability")

        # check to make sure that the originator has permission to increment
        # the FinalLiability
        if not liability_update.LiabilityObject.is_valid_object(
                store, self._final_liability_id):
            raise InvalidTransactionError(
                "Final liability does not reference a liability")

        # ensure that all of the offers are valid
        offermap = set()
        for offerid in self._offer_id_list:
            # make sure the offerid references a valid offer, note that a
            # selloffer is really just a subclass of exchangeoffer so a
            # selloffer is a valid exchange offer
            if not exchange_offer_update.ExchangeOfferObject.is_valid_object(
                    store, offerid):
                raise InvalidTransactionError(
                    "Offerid {} is not an ExchangeOffer".format(str(offerid)))
            # ensure that there are no duplicates in the list, duplicates can
            # cause of tests for validity to fail
            if offerid in offermap:
                logger.info('duplicate offers not allowed in an exchange; %s',
                            offerid)
                raise InvalidTransactionError("Duplicate offers not allowed")
            offermap.add(offerid)

        # and finally build the adjustment lists to make sure that all of the
        # adjustments are valid
        if not self.build_adjustment_list(store):
            logger.warn('failed to build the adjustment list')
            raise InvalidTransactionError(
                "Failed to build the adjustment list")

    def apply(self, store, txn):

        if not self.adjustment_list:
            self.build_adjustment_list(store)

        for adjustment in self.adjustment_list:
            adjustment.apply(store)

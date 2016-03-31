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
"""
Helper functions for creating and submitting marketplace transactions
"""

import logging
import os
import time

from twisted.web import http

from gossip import node, signed_object
from mktplace.transactions import account_update
from mktplace.transactions import asset_type_update
from mktplace.transactions import asset_update
from mktplace.transactions import exchange_offer_update
from mktplace.transactions import exchange_update
from mktplace.transactions import holding_update
from mktplace.transactions import liability_update
from mktplace.transactions import market_place
from mktplace.transactions import participant_update
from mktplace.transactions import sell_offer_update
from mktplace.mktplace_communication import MarketPlaceCommunication
from mktplace.mktplace_communication import MessageException
from mktplace.mktplace_state import MarketPlaceState

logger = logging.getLogger(__name__)


def interactive_client(url=None, name=None, keyfile=None):
    """
    InterativeClient -- utility function to simplify initialization of the
    MarketPlaceClient class in an interactive python shell.

    Args:
        url -- base url for a validator
        name -- simple name of a player, e.g. 'market'
        keyfile -- the name of the file from which keys should be retreived
    """

    if not url:
        url = 'http://localhost:8800/'
    if not name:
        name = 'market'
    if not keyfile:
        keyfile = "{0}/keys/{1}.wif".format(os.environ['CURRENCYHOME'], name)

    state = MarketPlaceState(url)
    state.fetch()

    creator = state.n2i('/player/{0}'.format(name))
    client = MarketPlaceClient(url,
                               creator=creator,
                               name=name,
                               keyfile=keyfile,
                               state=state)

    return client


class MarketPlaceClient(MarketPlaceCommunication):
    """
    The MarketPlaceClient class wraps transaction generation and
    submission for the Sawtooth Lake Digital Market.

    :param url baseurl: the base URL for a Sawtooth Lake validator that
        supports an HTTP interface
    :param id creator: the identifier for the participant generating
        transactions
    :param str keystring: the wif format key used to sign transactions
    :param str keyfile: the name of a file that contains the wif format key
    :param MarketPlaceState state : ledger state used to test correctness of
        transactions prior to submission
    """

    def __init__(self,
                 baseurl,
                 creator=None,
                 name='txnclient',
                 keystring=None,
                 keyfile=None,
                 state=None,
                 tokenstore=None):
        super(MarketPlaceClient, self).__init__(baseurl)

        self.CreatorID = creator
        self.LastTransaction = None

        self.CurrentState = state or MarketPlaceState(self.BaseURL)
        self.CurrentState.fetch()

        self.TokenStore = tokenstore

        # set up the signing key
        if keystring:
            logger.debug("set signing key from string\n%s", keystring)
            signingkey = signed_object.generate_signing_key(wifstr=keystring)
        elif keyfile:
            logger.debug("set signing key from file %s", keyfile)
            signingkey = signed_object.generate_signing_key(
                wifstr=open(keyfile, "r").read())
        else:
            raise TypeError('expecting valid signing key, none provided')

        identifier = signed_object.generate_identifier(signingkey)
        self.LocalNode = node.Node(identifier=identifier,
                                   signingkey=signingkey,
                                   name=name)

    def _sendtxn(self, update):
        """
        Build a transaction for the update, wrap it in a message with all
        of the appropriate signatures and post it to the validator
        """

        txn = market_place.MarketPlaceTransaction()
        txn.Update = update

        # add payment if we have a token repository
        if self.TokenStore:
            txn.Payment = self.TokenStore.get_tokens(1)

        # add the last transaction submitted to ensure that the ordering
        # in the journal matches the order in which we generated them
        if self.LastTransaction:
            txn.Dependencies = [self.LastTransaction]

        txn.Update.Transaction = txn
        if txn.Payment:
            txn.Payment.Transaction = txn

        txn.sign_from_node(self.LocalNode)
        txnid = txn.Identifier

        if not txn.is_valid(self.CurrentState.State):
            logger.warn('transaction failed to apply')
            return None

        msg = market_place.MarketPlaceTransactionMessage()
        msg.Transaction = txn
        msg.SenderID = self.LocalNode.Identifier
        msg.sign_from_node(self.LocalNode)

        try:
            result = self.postmsg(msg.MessageType, msg.dump())

        except MessageException as me:
            return None

        except:
            logger.exception('message post failed for some unusual reason')
            return None

        # if there was no exception thrown then all transactions should return
        # a value which is a dictionary with the message that was sent
        assert result

        # if the message was successfully posted, then save the transaction
        # id for future dependencies this could be a problem if the transaction
        # fails during application
        self.LastTransaction = txnid
        txn.apply(self.CurrentState.State)

        return txnid

    def _register(self, update):
        """
        Wrap a register transaction with a few additional checks to ensure that
        names are updated correctly.
        """

        # check to see if this name already exists
        if self.CurrentState.n2i(update.Name):
            logger.warn('attempt to register object with duplicate name %s',
                        update.Name)
            return None

        txnid = self._sendtxn(update)

        # the state *should* have been updated when we sent the transaction
        # successfully so there should be an object there, just need to update
        # the name map
        if txnid:
            fqname = self.CurrentState.i2n(txnid)
            self.CurrentState.bind(fqname, txnid)

        return txnid

    def _unregister(self, update):
        """
        Wrap an unregister transaction with a few additional checks to ensure
        that names are updated correctly.
        """

        fqname = self.CurrentState.i2n(update.ObjectID)
        txnid = self._sendtxn(update)

        # application of the unregister transaction should have removed the
        # state for the object, this just gets rid of the name mapping
        if txnid:
            self.CurrentState.unbind(fqname)

        return txnid

    def waitforcommit(self, txnid=None, timetowait=5, iterations=12):
        """
        Wait until a specified transaction shows up in the ledger's committed
        transaction list

        :param id txnid: the transaction to wait for, the last transaction by
            default
        :param int timetowait: time to wait between polling the ledger
        :param int iterations: number of iterations to wait before giving up
        """

        if not txnid:
            txnid = self.LastTransaction

        if not txnid:
            logger.info('no transaction specified for wait')
            return True

        passes = 0
        while True:
            passes += 1
            status = self.headrequest('/transaction/{0}'.format(txnid))

            if status == http.NOT_FOUND and passes > iterations:
                logger.warn('unknown transaction %s', txnid)
                return False

            if status == http.OK:
                return True

            logger.debug('waiting for transaction %s to commit', txnid)
            time.sleep(timetowait)

    def exchange(self, payer, payee, count, offerids=[]):
        """
        Generate an exchange transaction for moving assets amongst holdings

        :param id payer: the holding/liability from which assets will be
            transferred
        :param id payee: the holding/liability into which assets will be
            transferred
        :param int count: the number of assets that will be transferred from
            the payer holding/liability
        :param offerids: a list of offer identifiers that transform payer to
            payee transaction
        :type offerids list of id
        :return: exchange transaction id
        :rtype: id
        """
        update = exchange_update.Exchange()

        # Check current state for the correctness of the arguments

        update.InitialLiabilityID = payer
        update.FinalLiabilityID = payee
        update.InitialCount = count
        update.OfferIDList = offerids

        return self._sendtxn(update)

    def register_asset(self,
                       assettype,
                       name='',
                       description='',
                       consumable=True,
                       restricted=True,
                       divisible=False):
        """
        Register an asset with the ledger.

        :param id assettype: the asset type identifier
        :param str name: an optional name for the asset, unique for the current
            participant
        :param str description: an optional description for the asset

        :return: asset id
        :rtype: id
        """
        update = asset_update.Register()

        update.CreatorID = self.CreatorID
        update.AssetTypeID = assettype
        update.Name = name
        update.Description = description
        update.Consumable = consumable
        update.Restricted = restricted
        update.Divisible = divisible

        return self._register(update)

    def unregister_asset(self, objectid):
        """
        Unregister an asset.

        :param id objectid: the identifier for the asset object

        :return: unregister transaction identifier
        :rtype: id
        """
        update = asset_update.Unregister()

        update.CreatorID = self.CreatorID
        update.ObjectID = objectid

        return self._unregister(update)

    def register_assettype(self, name='', description='', restricted=True):
        """
        Register an asset type.

        :param str name: an optional name for the asset type, unique for the
            current participant
        :param str description: an optional description for the asset type

        :return: asset type id
        :rtype: id
        """
        update = asset_type_update.Register()

        update.CreatorID = self.CreatorID
        update.Name = name
        update.Description = description
        update.Restricted = restricted

        return self._register(update)

    def unregister_assettype(self, objectid):
        """
        Unregister an asset type.

        :param id objectid: the identifier for the asset type object

        :return: unregister transaction identifier
        :rtype: id
        """
        update = asset_type_update.Unregister()

        update.CreatorID = self.CreatorID
        update.ObjectID = objectid

        return self._unregister(update)

    def register_exchangeoffer(self, iliability, oliability, ratio, **kwargs):
        """
        Construct and post a transaction to register an exchange offer.

        :param id iliability: identifier for the input liability (where payment
            is made)
        :param id oliability: identifier for the output liability (where goods
            are given)
        :param str name: an optional name for the asset type, unique for the
            current participant
        :param str description: an optional description for the asset type
        :param int minimum: an optional parameter noting the smallest number of
            input assets
        :param int maximum: an optional parameter noting the largest number of
            input assets
        :param execution: optional flag indicating offer execution modifiers
        :type execution: one of 'Any', 'ExecuteOnce',
            'ExecuteOncePerParticipant'

        :return: exchange offer id
        :rtype: id
        """

        update = exchange_offer_update.Register()

        update.CreatorID = self.CreatorID
        update.InputID = iliability
        update.OutputID = oliability
        update.Ratio = float(ratio)

        if 'name' in kwargs:
            update.Name = kwargs['name']

        if 'description' in kwargs:
            update.Description = kwargs['description']

        if 'minimum' in kwargs:
            update.Minimum = int(kwargs['minimum'])

        if 'maximum' in kwargs:
            update.Maximum = int(kwargs['maximum'])

        if 'execution' in kwargs:
            update.Execution = kwargs['execution']

        return self._register(update)

    def unregister_exchangeoffer(self, objectid):
        """
        Revoke an exchange offer.

        :param id objectid: the identifier for the exchange offer

        :return: unregister transaction identifier
        :rtype: id
        """
        update = exchange_offer_update.Unregister()

        update.CreatorID = self.CreatorID
        update.ObjectID = objectid

        return self._unregister(update)

    def register_holding(self, account, asset, count, name='', description=''):
        """
        Register a holding.

        :param id account: the identifier the account that scopes the holding
        :param id asset: the identifier for the asset to store in the holding
        :param int count: the initial number of assets to store in the holding
        :param str name: an optional name for the holding, unique for the
            current participant
        :param str description: an optional description for the holding

        :return: holding id
        :rtype: id
        """
        update = holding_update.Register()

        update.CreatorID = self.CreatorID
        update.AccountID = account
        update.AssetID = asset
        update.Count = count
        update.Name = name
        update.Description = description

        return self._register(update)

    def unregister_holding(self, objectid):
        """
        Unregister a holding.

        :param id objectid: the identifier for the holding

        :return: unregister transaction identifier
        :rtype: id
        """
        update = holding_update.Unregister()

        update.CreatorID = self.CreatorID
        update.ObjectID = objectid

        return self._unregister(update)

    def register_liability(self,
                           account,
                           assettype,
                           guarantor,
                           count,
                           name='',
                           description=''):
        """
        Register a liability.

        :param id account: the identifier the account that scopes the liability
        :param id assettype: the identifier for the asset type to store in the
            liability
        :param int count: the initial number of assets to store in the
            liability
        :param str name: an optional name for the liability, unique for the
            current participant
        :param str description: an optional description for the liability

        :return: liability id
        :rtype: id
        """
        update = liability_update.Register()

        update.CreatorID = self.CreatorID
        update.AccountID = account
        update.AssetTypeID = assettype
        update.GuarantorID = guarantor if guarantor else self.CreatorID
        update.Count = count
        update.Name = name
        update.Description = description

        return self._register(update)

    def unregister_liability(self, objectid):
        """
        Unregister a liability.

        :param id objectid: the identifier for the liability

        :return: unregister transaction identifier
        :rtype: id
        """
        update = liability_update.Unregister()

        update.CreatorID = self.CreatorID
        update.ObjectID = objectid

        return self._unregister(update)

    def register_participant(self, name='', description=''):
        """
        Register a participant with the ledger.

        :param str name: an optional name for the asset, unique for the current
            participant
        :param str description: an optional description for the asset

        :return: participant id
        :rtype: id
        """
        update = participant_update.Register()

        update.Name = name
        update.Description = description

        return self._register(update)

    def unregister_participant(self, objectid):
        """
        Unregister a participant.

        :param id objectid: the identifier for the participant

        :return: unregister transaction identifier
        :rtype: id
        """
        update = participant_update.Unregister()

        update.CreatorID = self.CreatorID
        update.ObjectID = objectid

        return self._unregister(update)

    def register_selloffer(self, iliability, oholding, ratio, **kwargs):
        """
        Construct and post a transaction to register an SellOffer object

        :param id iliability: identifier for the input liability (where payment
            is made)
        :param id oholding: identifier for the output holding (where goods are
            given)
        :param str name: an optional name for the asset type, unique for the
            current participant
        :param str description: an optional description for the asset type
        :param int minimum: an optional parameter noting the smallest number of
            input assets
        :param int maximum: an optional parameter noting the largest number of
            input assets
        :param execution: optional flag indicating offer execution modifiers
        :type execution: one of 'Any', 'ExecuteOnce',
            'ExecuteOncePerParticipant'

        :return: exchange offer id
        :rtype: id
        """

        update = sell_offer_update.Register()

        update.CreatorID = self.CreatorID
        update.InputID = iliability
        update.OutputID = oholding
        update.Ratio = float(ratio)

        if 'name' in kwargs:
            update.Name = kwargs['name']

        if 'description' in kwargs:
            update.Description = kwargs['description']

        if 'minimum' in kwargs:
            update.Minimum = int(kwargs['minimum'])

        if 'maximum' in kwargs:
            update.Maximum = int(kwargs['maximum'])

        if 'execution' in kwargs:
            update.Execution = kwargs['execution']

        return self._register(update)

    def unregister_selloffer(self, objectid):
        """
        Revoke a sell offer.

        :param id objectid: the identifier for the sell offer

        :return: unregister transaction identifier
        :rtype: id
        """
        update = sell_offer_update.Unregister()

        update.CreatorID = self.CreatorID
        update.ObjectID = objectid

        return self._unregister(update)

    def register_account(self, name='', description=''):
        """
        Register an account with the ledger.

        :param str name: an optional name for the asset, unique for the current
            participant
        :param str description: an optional description for the asset

        :return: account id
        :rtype: id
        """
        update = account_update.Register()

        update.CreatorID = self.CreatorID
        update.Name = name
        update.Description = description

        return self._register(update)

    def unregister_account(self, objectid):
        """
        Unregister an account.

        :param id objectid: the identifier for the account

        :return: unregister transaction identifier
        :rtype: id
        """
        update = account_update.Unregister()

        update.CreatorID = self.CreatorID
        update.ObjectID = objectid

        return self._unregister(update)

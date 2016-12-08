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
import hashlib
import logging
import os
import time

from twisted.web import http

from sawtooth_signing import pbct_nativerecover as signing
from gossip import node, signed_object
from gossip.common import dict2cbor
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

    creator = state.n2i('/player/{0}'.format(name), 'Participant')
    client = MarketPlaceClient(url,
                               creator=creator,
                               name=name,
                               keyfile=keyfile,
                               state=state)

    return client


def sign_message_with_transaction(transaction, key):
    """
    Signs a transaction message or transaction
    :param transaction dict:
    :param key str: A signing key
    returns message, txnid tuple: The first 16 characters
    of a sha256 hexdigest.
    """
    transaction['Nonce'] = time.time()
    pub = signing.encode_pubkey(signing.generate_pubkey(key), "hex")
    transaction["PublicKey"] = pub
    sig = signing.sign(dict2cbor(transaction), key)
    transaction['Signature'] = sig

    txnid = hashlib.sha256(transaction['Signature']).hexdigest()[:16]
    message = {
        'Transaction': transaction,
        '__TYPE__': "/mktplace.transactions.MarketPlace/Transaction",
        '__NONCE__': time.time(),
    }
    cbor_serialized_mess = dict2cbor(message)
    signature = signing.sign(cbor_serialized_mess, key)
    message['__SIGNATURE__'] = signature
    return message, txnid


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
    :param MarketPlaceState state: ledger state used to test correctness of
        transactions prior to submission
    """

    def __init__(self,
                 baseurl,
                 creator=None,
                 name='txnclient',
                 keystring=None,
                 keyfile=None,
                 state=None,
                 tokenstore=None,
                 session=False):
        super(MarketPlaceClient, self).__init__(baseurl)

        self.CreatorID = creator
        self.LastTransaction = None

        self.CurrentState = state or MarketPlaceState(self.BaseURL)

        self.TokenStore = tokenstore

        self.enable_session = session
        logger.debug("self.enable_session: %s", self.enable_session)

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

    def _sendtxn(self, update, dependencies=None):
        """
        Sends the transaction to the validator, if enable_session is True,
        the txns are sent to the prevalidation page first to be validated
        :param update dict: The txn family specific data model items needed
        :return txnid str: The first 16 characters of a sha256 hexdigest.
        """
        transaction = {'TransactionType': "/MarketPlaceTransaction"}
        transaction['Updates'] = [update]
        if dependencies is None:
            transaction['Dependencies'] = []
        else:
            transaction['Dependencies'] = list(dependencies)

        msg, txnid = sign_message_with_transaction(
            transaction,
            self.LocalNode.SigningKey
        )
        try:
            if self.enable_session:
                result = self.postmsg(
                    "/mktplace.transactions.MarketPlace/Transaction",
                    msg,
                    '/prevalidation'
                )
            else:
                result = self.postmsg(
                    "/mktplace.transactions.MarketPlace/Transaction",
                    msg
                )

        except MessageException:
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
        if self.enable_session:
            storeinfo = self.getmsg('/prevalidation')
            self.CurrentState.State = \
                self.CurrentState.State.clone_store(storeinfo)
        return txnid

    def create_session(self):
        self.enable_session = True

    def delete_session(self):
        try:
            if self.enable_session:
                self.headrequest('/prevalidation')
                self.enable_session = False

        except MessageException:
            pass

        except:
            logger.exception('message post failed for some unusual reason')

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

    def exchange(self, payer, payee, count, offerids=None):
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
        :type offerids: list of id
        :return: exchange transaction id
        :rtype: id
        """
        update = {
            'UpdateType': 'Exchange',
            'InitialLiabilityId': payer,
            'FinalLiabilityId': payee, 'OfferIdList': offerids or [],
            'InitialCount': count
        }

        return self._sendtxn(update, dependencies=[
            payer, payee
        ] + offerids)

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
        update = {
            'UpdateType': 'RegisterAsset',
            'AssetTypeId': assettype,
            'Name': name,
            'Description': description,
            'CreatorId': self.CreatorID,
            'Consumable': consumable,
            'Restricted': restricted,
            'Divisible': divisible
        }
        return self._sendtxn(update, dependencies=[self.CreatorID, assettype])

    def unregister_asset(self, objectid):
        """
        Unregister an asset.

        :param id objectid: the identifier for the asset object

        :return: unregister transaction identifier
        :rtype: id
        """
        update = {
            'UpdateType': 'UnregisterAsset',
            'ObjectId': objectid,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_asset_name(self, objectid, name):
        update = {
            'UpdateType': 'UpdateAssetName',
            'ObjectId': objectid,
            'Name': name,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_asset_description(self, objectid, description):
        update = {
            'UpdateType': 'UpdateAssetDescription',
            'ObjectId': objectid,
            'Description': description,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def register_assettype(self, name='', description='', restricted=True):
        """
        Register an asset type.

        :param str name: an optional name for the asset type, unique for the
            current participant
        :param str description: an optional description for the asset type

        :return: asset type id
        :rtype: id
        """
        update = {
            'UpdateType': 'RegisterAssetType',
            'Name': name,
            'Description': description,
            'Restricted': restricted,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update, dependencies=[self.CreatorID])

    def unregister_assettype(self, objectid):
        """
        Unregister an asset type.

        :param id objectid: the identifier for the asset type object

        :return: unregister transaction identifier
        :rtype: id
        """
        update = {
            'UpdateType': 'UnregisterAssetType',
            'ObjectId': objectid,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_assettype_name(self, objectid, name):
        update = {
            'UpdateType': 'UpdateAssetTypeName',
            'ObjectId': objectid,
            'Name': name,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_assettype_description(self, objectid, description):
        update = {
            'UpdateType': 'UpdateAssetTypeDescription',
            'ObjectId': objectid,
            'Description': description,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

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
        update = {
            'UpdateType': 'RegisterExchangeOffer',
            'CreatorId': self.CreatorID,
            'InputId': iliability,
            'OutputId': oliability,
            'Ratio': float(ratio),
            'Minimum': kwargs.get('minimum', 1),
            'Maximum': kwargs.get('maximum', 20000000000),
            'Name': kwargs.get('name', ''),
            'Description': kwargs.get('description', ''),
            'Execution': kwargs.get('execution', 'Any')
        }
        return self._sendtxn(update, dependencies=[
            iliability, oliability, self.CreatorID])

    def unregister_exchangeoffer(self, objectid):
        """
        Revoke an exchange offer.

        :param id objectid: the identifier for the exchange offer

        :return: unregister transaction identifier
        :rtype: id
        """
        update = {
            'UpdateType': 'UnregisterExchangeOffer',
            'ObjectId': objectid,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_exchangeoffer_name(self, objectid, name):
        update = {
            'UpdateType': 'UpdateExchangeOfferName',
            'ObjectId': objectid,
            'Name': name,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_exchangeoffer_description(self, objectid, description):
        update = {}
        update['ObjectId'] = objectid
        update['Description'] = description
        return self._sendtxn(update)

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
        update = {
            'UpdateType': 'RegisterHolding',
            'AccountId': account,
            'AssetId': asset,
            'Count': count,
            'CreatorId': self.CreatorID,
            'Name': name,
            'Description': description
        }
        return self._sendtxn(update, dependencies=[
            self.CreatorID, account, asset
        ])

    def unregister_holding(self, objectid):
        """
        Unregister a holding.

        :param id objectid: the identifier for the holding

        :return: unregister transaction identifier
        :rtype: id
        """
        update = {
            'UpdateType': 'UnregisterHolding',
            'ObjectId': objectid,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_holding_name(self, objectid, name):
        update = {
            'UpdateType': 'UpdateHoldingName',
            'ObjectId': objectid,
            'Name': name,
            'CreatorId': self.CreatorID
        }
        self._sendtxn(update)

    def update_holding_description(self, objectid, description):
        update = {
            'UpdateType': 'UpdateHoldingDescription',
            'ObjectId': objectid,
            'Description': description,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

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
        update = {
            'UpdateType': 'RegisterLiability',
            'AccountId': account,
            'AssetTypeId': assettype,
            'GuarantorId': guarantor,
            'CreatorId': self.CreatorID,
            'Count': count,
            'Name': name,
            'Description': description
        }
        return self._sendtxn(update, dependencies=[
            self.CreatorID, assettype
        ])

    def unregister_liability(self, objectid):
        """
        Unregister a liability.

        :param id objectid: the identifier for the liability

        :return: unregister transaction identifier
        :rtype: id
        """
        update = {
            'UpdateType': 'UnregisterLiability',
            'ObjectId': objectid,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_liability_name(self, objectid, name):
        update = {
            'UpdateType': 'UpdateLiabilityName',
            'ObjectId': objectid,
            'Name': name,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_liability_description(self, objectid, description):
        update = {
            'UpdateType': 'UpdateLiabilityDescription',
            'ObjectId': objectid,
            'Description': description,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def register_participant(self, name='', description=''):
        """
        Register a participant with the ledger.

        :param str name: an optional name for the asset, unique for the current
            participant
        :param str description: an optional description for the asset

        :return: participant id
        :rtype: id
        """
        update = {
            'UpdateType': 'RegisterParticipant',
            'Name': name,
            'Description': description
        }
        return self._sendtxn(update)

    def unregister_participant(self, objectid):
        """
        Unregister a participant.

        :param id objectid: the identifier for the participant

        :return: unregister transaction identifier
        :rtype: id
        """
        update = {
            'UpdateType': 'UnregisterParticipant',
            'ObjectId': objectid,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_participant_name(self, objectid, name):
        update = {
            'UpdateType': 'UpdateParticipantName',
            'ObjectId': objectid,
            'Name': name,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_participant_description(self, objectid, description):
        update = {
            'UpdateType': 'UpdateParticipantDescription',
            'ObjectId': objectid,
            'Description': description,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

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
        update = {
            'UpdateType': 'RegisterSellOffer',
            'CreatorId': self.CreatorID,
            'InputId': iliability,
            'OutputId': oholding,
            'Ratio': float(ratio),
            'Name': kwargs.get('name', ''),
            'Description': kwargs.get('description', ''),
            'Minimum': kwargs.get('minimum', 0),
            'Maximum': kwargs.get('maximum', 2000000000000000),
            'Execution': kwargs.get('execution', 'Any')
        }
        return self._sendtxn(update, dependencies=[
            self.CreatorID, iliability, oholding
        ])

    def unregister_selloffer(self, objectid):
        """
        Revoke a sell offer.

        :param id objectid: the identifier for the sell offer

        :return: unregister transaction identifier
        :rtype: id
        """
        update = {
            'UpdateType': 'UnregisterSellOffer',
            'ObjectId': objectid,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_selloffer_name(self, objectid, name):
        update = {
            'UpdateType': 'UpdateSellOfferName',
            'ObjectId': objectid,
            'Name': name,
            'CreatorId': self.CreatorID
        }

        return self._sendtxn(update)

    def update_selloffer_description(self, objectid, description):
        update = {
            'UpdateType': "UpdateSellOfferDescription",
            'ObjectId': objectid,
            'Description': description,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def register_account(self, name='', description=''):
        """
        Register an account with the ledger.

        :param str name: an optional name for the asset, unique for the current
            participant
        :param str description: an optional description for the asset

        :return: account id
        :rtype: id
        """
        update = {
            'UpdateType': 'RegisterAccount',
            'Name': name,
            'Description': description,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update, dependencies=[self.CreatorID])

    def unregister_account(self, objectid):
        """
        Unregister an account.

        :param id objectid: the identifier for the account

        :return: unregister transaction identifier
        :rtype: id
        """
        update = {
            'UpdateType': 'UnregisterAccount',
            'ObjectId': objectid,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_account_name(self, objectid, name):
        update = {
            'UpdateType': 'UpdateAccountName',
            'ObjectId': objectid,
            'Name': name,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

    def update_account_description(self, objectid, description):
        update = {
            'UpdateType': 'UpdateAccountDescription',
            'ObjectId': objectid,
            'Description': description,
            'CreatorId': self.CreatorID
        }
        return self._sendtxn(update)

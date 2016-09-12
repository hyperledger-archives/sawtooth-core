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

from journal.transaction import Status
from mktplace import mktplace_client, mktplace_state, mktplace_communication
from txnintegration.utils import generate_private_key
from txnintegration.utils import get_address_from_private_key_wif
from txnintegration.utils import random_name


class MktActor(object):
    """
    This is a simplification of the MktPlace transaction client

    Each actor has:
    1 Account (/account) all holdings are registered as /account/{asset name}
    1 Asset type (/assets) all assets are registered as /assets/{asset name}

    holdings for assets will be automatically created if needed.



    This expects all assets to be uniquely named (stronger restriction than the
    mktplace transaction family)
    """

    def __init__(self, name, ledger_url, key=None, state=None):
        # record of all transactions this actor has committed
        self.transactions = []

        self.accounts = None
        self.assetType = None
        self.assets = {}
        self.holdings = {}  # map, fully qualified names
        self.holdingsByAsset = {}  # map, fqn asset to fqn holding id.
        self.Name = name
        self.state = state
        if self.state is None:
            self.state = mktplace_state.MarketPlaceState(ledger_url)

        # create keys
        # Generate key for validator
        self.Key = key
        if not self.Key:
            self.Key = generate_private_key()

        self.creator = self.state.n2i('//{0}'.format(name), 'Participant')
        if self.creator:
            addr = get_address_from_private_key_wif(self.Key)
            partxn = self.state.State[self.creator]
            if addr != partxn["address"]:
                raise Exception("Participant key mismatch")

        self.client = mktplace_client.MarketPlaceClient(ledger_url,
                                                        creator=self.creator,
                                                        name=name,
                                                        keystring=self.Key,
                                                        state=self.state)

        if not self.creator:
            self.creator = self.client.register_participant(name)
            self.client.CreatorID = self.creator
            self.transactions.append(self.creator)

        if not self.creator:
            raise

        self.state.CreatorID = self.creator
        self._register_account()
        self._register_asset_type()

        # LOAD objects from state
        for no in self.state.list(creator=self.creator, fields="*"):
            n = no['name']
            obj_type = no['object-type']
            if n.startswith(self.get_qualified_name("/assets/")):
                o = self.get_state_object(n, obj_type)
                if self.creator != o["creator"]:
                    raise Exception("Transaction namespace violation.")
                self.assets[n] = no
            elif n.startswith(self.get_qualified_name("/assets")):
                o = self.get_state_object(n, obj_type)
                if self.creator != o["creator"]:
                    raise Exception("Transaction namespace violation.")
                self.assetType = no
            elif n.startswith(self.get_qualified_name("/account/")):
                o = self.get_state_object(n, obj_type)
                if self.creator != o["creator"]:
                    raise Exception("Transaction namespace violation.")
                self.holdings[n] = self.state.NameMap[n]
                asset_name = self.state.i2n(o["asset"])
                self.holdingsByAsset[asset_name] = no

    def update(self):
        self.state.fetch()

    def get_state_object(self, name, obj_type):
        id = self.state.n2i(name, obj_type)
        if id:
            return self.state.State[id]
        elif name in self.state.State:
            return self.state.State[name]
        return None

    def get_holding_id(
            self,
            name):  # name may be holding(FQN), asset(FQN), assetId, holdingId
        if name in self.holdings:
            return self.holdings[name]
        elif name in self.holdingsByAsset:
            return self.holdingsByAsset[name]
        elif name in self.state.State:
            o = self.state.State[name]
            if o["object-type"] == "Asset":
                n = self.state.i2n(name)
                return self.holdingsByAsset[n]
            elif o["object-type"] == "Holding":
                raise Exception("Unable to resolve {} to asset.".format(name))
        else:
            raise Exception("Unable to resolve {} to asset.".format(name))

        return None

    def get_qualified_name(self, name):  # Fully qualified name to object
        return "//{}{}".format(self.Name, name)

    def _verify_transaction_id(self, txnid):  # Fully qualified name to object
        if not txnid:
            raise Exception("Transaction failed to post.")
        self.transactions.append(txnid)

    def _register_account(self):
        self.account = self.state.n2i('//{0}/account'.format(self.Name),
                                      'Account')
        if not self.account:
            self.account = self.client.register_account("/account")
            self._verify_transaction_id(self.account)
        return self.account

    def _register_asset_type(self):
        self.assetType = self.state.n2i('//{0}/assets'.format(self.Name),
                                        'AssetType')
        if not self.assetType:
            self.assetType = self.client.register_assettype(name="/assets",
                                                            restricted=True)
            self._verify_transaction_id(self.assetType)
        return self.assetType

    def register_asset(self, name):
        name = "/assets/{}".format(name)
        fqn = self.get_qualified_name(name)
        if fqn not in self.assets:
            txnid = self.client.register_asset(name=name,
                                               assettype=self.assetType,
                                               restricted=True)
            self._verify_transaction_id(txnid)
            self.assets[fqn] = txnid
            return txnid
        else:
            return self.assets[fqn]

    def register_holding(self, asset_name, count=0):

        asset = self.get_state_object(asset_name, 'Asset')
        assetId = asset['object-id']

        name = "/account{}".format(asset["name"])
        fqn = self.get_qualified_name(name)
        if fqn not in self.holdings:
            txnid = self.client.register_holding(name=name,
                                                 account=self.account,
                                                 asset=assetId,
                                                 count=count)
            self._verify_transaction_id(txnid)
            self.holdings[fqn] = txnid
            self.holdingsByAsset[asset_name] = txnid
            return txnid
        else:
            return self.holdings[fqn]

    def register_exchange_offer(self,
                                inAssetFqn,
                                inAmount,
                                outAssetFqn,
                                outAmount,
                                inMin=1,
                                inMax=1,
                                execution='ExecuteOnce'):
        # inAssetFqn - the fqn of the asset agent is to receive(purchase)
        # outAssetFqn - the fqn of the asset agent is to give(pay)
        #: execution: one of 'Any', 'ExecuteOnce', 'ExecuteOncePerParticipant'

        inHolding = self.get_holding_id(inAssetFqn)
        outHolding = self.get_holding_id(outAssetFqn)
        ratio = float(inAmount) / float(outAmount)

        txnid = self.client.register_exchangeoffer(inHolding,
                                                   outHolding,
                                                   ratio,
                                                   name=random_name(),
                                                   minimum=inMin,
                                                   maximum=inMax,
                                                   execution=execution)
        self._verify_transaction_id(txnid)
        return txnid

    def register_sell_offer(self,
                            inAssetFqn,
                            inAmount,
                            outAssetFqn,
                            outAmount,
                            inMin=1,
                            inMax=1):
        inHolding = self.get_holding_id(inAssetFqn)
        outHolding = self.get_holding_id(outAssetFqn)
        ratio = float(inAmount) / float(outAmount)

        txnid = self.client.register_selloffer(inHolding,
                                               outHolding,
                                               ratio,
                                               minimum=inMin,
                                               maximum=inMax)
        self._verify_transaction_id(txnid)
        return txnid

    def exchange(self, offerId, amount=1):
        offer = self.state.State[offerId]
        offerInputAsset = self.get_state_object(offer["input"],
                                                'Holding')["asset"]
        offerOutputAsset = self.get_state_object(offer["output"],
                                                 'Holding')["asset"]

        payingHolding = self.get_holding_id(offerInputAsset)
        receivingHolding = self.get_holding_id(offerOutputAsset)

        txnid = self.client.exchange(payingHolding,
                                     receivingHolding,
                                     amount,
                                     offerids=[offerId])
        self._verify_transaction_id(txnid)
        return txnid

    def has_uncommitted_transactions(self):
        remaining = []
        for t in self.transactions:
            try:
                r = self.client.getmsg('/transaction/{0}'.format(t))
                s = r["Status"]
                if s == Status.pending:
                    remaining.append(t)
                elif s == Status.failed:
                    print r
                    raise Exception(
                        "Transaction {} failed to validate.".format(t))
                elif s == Status.unknown:
                    print r
                    raise Exception(
                        "Transaction {} is in unknown state, everybody "
                        "panic.".format(t))
            except mktplace_communication.MessageException as e:
                # this is caused by the transaction not being propagated to
                # the validator yet or the validator still working on
                # processing the transaction
                print "Ignoring validator error response: ", e

        self.transactions = remaining
        return len(self.transactions)

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
import random
import string
import hashlib

from gossip.common import dict2cbor
from sawtooth.client import SawtoothClient


LOGGER = logging.getLogger(__name__)


def create_nonce():
    return ''.join(
        [random.choice(string.ascii_letters) for _ in xrange(0, 16)])


class BondClient(SawtoothClient):
    def __init__(self,
                 base_url,
                 keyfile=None):
        super(BondClient, self).__init__(
            base_url=base_url,
            store_name='BondTransaction',
            name='BondClient',
            keyfile=keyfile,
            txntype_name='/BondTransaction',
            msgtype_name='/Bond/Transaction'
        )

    def send_bond_update(self, update):
        return self.send_update(update)

    def create_participant(self, username, firm_id=None, object_id=None):
        update = {'UpdateType': 'CreateParticipant',
                  'Username': username}
        if firm_id is not None:
            update['FirmId'] = firm_id
        if object_id is not None:
            update['ObjectId'] = object_id
        else:
            update['ObjectId'] = hashlib.sha256(dict2cbor(update)).hexdigest()
        return self.send_bond_update(update)

    def update_participant(self, object_id, username=None, firm_id=None):
        update = {'UpdateType': 'UpdateParticipant',
                  'ObjectId': object_id,
                  'Nonce': create_nonce()}
        if username is not None:
            update['Username'] = username
        if firm_id is not None:
            update['FirmId'] = firm_id
        return self.send_bond_update(update)

    def create_org(self, name, object_id=None, industry=None, ticker=None,
                   pricing_src=None, authorization=None):
        update = {'UpdateType': 'CreateOrganization',
                  'Name': name,
                  'Nonce': create_nonce()}
        obj = {'ObjectId': object_id, 'Industry': industry,
               'Ticker': ticker, 'PricingSource': pricing_src,
               'Authorization': authorization}
        for k, v in obj.iteritems():
            if v is not None:
                update[k] = v
        if "ObjectId" not in update:
            update["ObjectId"] = hashlib.sha256(dict2cbor(update)).hexdigest()
        return self.send_bond_update(update)

    def add_authorization_to_org(self, object_id, role, participant_id=None):
        """
            Add an authorization (participant/role combination) to an
            organization.
        Args:
            object_id: The object ID of the organization
            role: (str) "marketmaker" or "trader"
            participant_id: The participant ID that grants the authorization
                            or None to indicate the participant that created
                            the organization.

        Returns:
            Transaction ID
        """
        update = {'UpdateType': 'UpdateOrganizationAuthorization',
                  'ObjectId': object_id,
                  'Action': 'add',
                  'Role': role,
                  'Nonce': create_nonce()}
        if participant_id is not None:
            update['ParticipantId'] = participant_id
        if "ObjectId" not in update:
            update["ObjectId"] = hashlib.sha256(dict2cbor(update)).hexdigest()
        return self.send_bond_update(update)

    def create_order(self, action, order_type, firm_id, quantity,
                     isin=None, cusip=None, limit_price=None,
                     limit_yield=None, object_id=None):
        update = {'UpdateType': 'CreateOrder',
                  'Action': action, 'OrderType': order_type,
                  'FirmId': firm_id, 'Quantity': quantity,
                  'Nonce': create_nonce()}
        possible_updates = {'Isin': isin, 'Cusip': cusip,
                            'LimitPrice': limit_price,
                            'LimitYield': limit_yield,
                            'ObjectId': object_id}
        for k, v in possible_updates.iteritems():
            if v is not None:
                update[k] = v
        if "ObjectId" not in update:
            update["ObjectId"] = hashlib.sha256(dict2cbor(update)).hexdigest()
        return self.send_bond_update(update)

    def create_quote(self, firm, ask_qty, ask_price, bid_qty, bid_price,
                     isin=None, cusip=None, object_id=None):
        update = {'UpdateType': 'CreateQuote',
                  'Firm': firm, 'AskQty': ask_qty,
                  'AskPrice': ask_price,
                  'BidQty': bid_qty, 'BidPrice': bid_price,
                  'Nonce': create_nonce()}
        if isin is not None:
            update['Isin'] = isin
        if cusip is not None:
            update['Cusip'] = cusip
        if object_id is not None:
            update['ObjectId'] = object_id
        if "ObjectId" not in update:
            update["ObjectId"] = hashlib.sha256(dict2cbor(update)).hexdigest()
        return self.send_bond_update(update)

    def create_settlement(self, order_id, object_id=None):
        update = {'UpdateType': 'CreateSettlement',
                  'OrderId': order_id,
                  'Nonce': create_nonce()}
        if object_id is not None:
            update['ObjectId'] = object_id
        if "ObjectId" not in update:
            update["ObjectId"] = hashlib.sha256(dict2cbor(update)).hexdigest()
        return self.send_bond_update(update)

    def create_holding(self, owner_id, asset_type, asset_id,
                       amount, object_id=None):
        update = {'UpdateType': 'CreateHolding',
                  'OwnerId': owner_id, 'AssetType': asset_type,
                  'AssetId': asset_id, 'Amount': amount,
                  'Nonce': create_nonce()}
        if object_id is not None:
            update['ObjectId'] = object_id
        if "ObjectId" not in update:
            update["ObjectId"] = hashlib.sha256(dict2cbor(update)).hexdigest()
        return self.send_bond_update(update)

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
from datetime import datetime, date

from sawtooth.client import SawtoothClient
from gossip import signed_object

from sawtooth_bond.updates.libor import LIBORObject
from sawtooth_bond.txn_family import BondTransaction
from sawtooth_signing import pbct_nativerecover as signing

from libor.libor_exceptions import LIBORClientException

LOGGER = logging.getLogger(__name__)


class LIBORClient(SawtoothClient):
    def __init__(self, base_url, key_file, libor_key_file=None):
        super(LIBORClient, self).__init__(
            base_url=base_url,
            store_name='BondTransaction',
            name='BondClient',
            keyfile=key_file,
            transaction_type=BondTransaction,
            message_type=BondTransaction.MessageType)
        self._libor_key_file = libor_key_file

    def submit_rates(self, effective_date, rates):
        """Submit a set of rates to the blockchain.

        Args:
            effective_date: The date the rates were published.  This may be
                provided as either a string in ISO-8601 format ("YYYY-MM-DD"),
                a datetime, or a date object.
            rate: A dictionary mapping maturity periods to rate values.  The
                following keys must be present:  Overnight, OneWeek, OneMonth,
                TwoMonth, ThreeMonth, SixMonth, OneYear
        """
        if self._libor_key_file is None:
            raise LIBORClientException(
                "Submitting LIBOR data requires a LIBOR signing key")

        # If we have a datetime or date object, get the ISO-8601 format string
        if isinstance(effective_date, datetime):
            effective_date = effective_date.date().isoformat()
        elif isinstance(effective_date, date):
            effective_date = effective_date.isoformat()

        signing_key = \
            signed_object.generate_signing_key(
                wifstr=open(self._libor_key_file, "r").read().strip())
        libor_public_key = signing.generate_pubkey(signing_key)
        # Add a signature to the actual update to simulate having a verified
        # source of information
        signed_update = LIBORObject(date=effective_date,
                                    rates=rates,
                                    libor_public_key=libor_public_key)
        signed_update.sign_object(signing_key)

        # Create the update and the submit the transaction
        update = {'UpdateType': 'CreateLIBOR'}
        update.update(signed_update.dump())

        return self.sendtxn(
            BondTransaction,
            BondTransaction.MessageType,
            {'Updates': [update]})

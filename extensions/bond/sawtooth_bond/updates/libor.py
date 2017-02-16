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
import math

from datetime import datetime

from gossip import signed_object
from sawtooth.exceptions import InvalidTransactionError
from journal.transaction import Update
from sawtooth_signing import pbct_nativerecover as signing

LOGGER = logging.getLogger(__name__)


class LIBORObject(signed_object.SignedObject):
    """LIBOR object encapsulates the attributes that represent LIBOR
    data, specifically the date and the rates.  This is used to wrap the
    LIBOR data to make verifying signatures more convenient.
    """

    def __init__(self, date, rates, libor_public_key, libor_signature=None):
        """

        Args:
            date: Date LIBOR was published as a string in ISO-8601 format
                ("YYYY-MM-DD")
            rates: A dictionary of LIBORs with the following keys:
                Overnight: The overnight LIBOR
                OneWeek: The one-week LIBOR
                OneMonth: The one-month LIBOR
                TwoMonth: The two-month LIBOR
                ThreeMonth: The three-month LIBOR
                SixMonth: The six-month LIBOR
                OneYear: The one-month LIBOR
            public_key: Public key corresponding to private key used to
                        sign the LIBOR data.
            signature: A signature over the LIBOR data (date and rates)
        """
        super(LIBORObject, self).__init__(
            minfo={
                'LiborPublicKey': libor_public_key,
                'LiborSignature': libor_signature
            }, sig_dict_key='LiborSignature', pubkey_dict_key='LiborPublicKey')

        self._date = date

        # Copy the rates, but also sanitize the data while we are at it.  Any
        # invalid float values will become NaN, which we will check later when
        # we are asked to check for valid data.
        # This will now cause the transactions to fail. The transactions are
        # being signed by the client before this sanitization is done, thus
        # creating a invalid signature.
        self._rates = {
            'Overnight': self.to_float(rates.get('Overnight')),
            'OneWeek': self.to_float(rates.get('OneWeek')),
            'OneMonth': self.to_float(rates.get('OneMonth')),
            'TwoMonth': self.to_float(rates.get('TwoMonth')),
            'ThreeMonth': self.to_float(rates.get('ThreeMonth')),
            'SixMonth': self.to_float(rates.get('SixMonth')),
            'OneYear': self.to_float(rates.get('OneYear'))
        }

    def get_date(self):
        return self._date

    def set_date(self, value):
        self._date = value

    date = property(get_date, set_date)

    @property
    def rates(self):
        return self._rates

    @ staticmethod
    def to_float(value):
        """A helper method that will convert a value to a float if it can
        and NaN if it is not possible to create a float from it

        Args:
            value: The value to convert to float
        """

        try:
            return float(value)
        except (TypeError, ValueError):
            pass

        return float('NaN')

    def dump(self):
        """
        Returns a dict with attributes from the object
        """
        result = super(LIBORObject, self).dump()
        result['Date'] = self._date
        result['Rates'] = self._rates

        return result


class CreateLIBORUpdate(Update):

    def __init__(self,
                 update_type,
                 date,
                 rates,
                 public_key=None,
                 signature=None,
                 libor_public_key=None,
                 libor_signature=None,
                 object_id=None):
        """
        Create a LIBOR update object.

        Args:
            update_type: Set to "CreateLIBOR"
            date: Date LIBOR was published as a string in ISO-8601 format
                ("YYYY-MM-DD")
            rates: A dictionary of LIBORs with the following keys:
                Overnight: The overnight LIBOR
                OneWeek: The one-week LIBOR
                OneMonth: The one-month LIBOR
                TwoMonth: The two-month LIBOR
                ThreeMonth: The three-month LIBOR
                SixMonth: The six-month LIBOR
                OneYear: The one-month LIBOR
            libor_public_key: Public key corresponding to private key
                used to sign the LIBOR data.
            signature: A signature over the LIBOR data (date and rates)
            object_id: An optional object ID for the update.  Much like a
                lawyer when you are arrested, if you don't provide one,
                one will be provided for you.
        """
        super(CreateLIBORUpdate, self).__init__(update_type=update_type)

        if object_id is None:
            self._object_id = 'libor.{}'.format(self.date_to_isoformat(date))
        else:
            self._object_id = object_id
        self.__libor_object__ = LIBORObject(date,
                                            rates,
                                            libor_public_key,
                                            libor_signature)
        self.__public_key = public_key
        self.__signature = signature
        self._rates = self.__libor_object__.rates

    @property
    def _date(self):
        return self.__libor_object__.date

    @property
    def _signature(self):
        return self.__signature

    @property
    def _public_key(self):
        return self.__public_key

    @property
    def _libor_signature(self):
        return self.__libor_object__.Signature

    @property
    def _libor_public_key(self):
        return self.__libor_object__.public_key

    def sign_update_object(self, signingkey):
        """Generates a string signature for the LIBOR data using the signing
        key.

        Args:
            signingkey (str): hex encoded private key
        """
        self.__libor_object__.sign_object(signingkey)

    @staticmethod
    def date_to_isoformat(date):
        """
        Returns a truly ISO-8601 formatted string.  It turns out that
        strptime() is slightly lenient in its interpretation (it allows
        for single-digit month and date) and we need to be absolutely certain
        that the date string is YYYY-MM-DD.

        Args:
            date: A date string to make truly ISO-8601

        Returns:
            A ISO-8601 format date string on success, None on failure.
        """
        try:
            return datetime.strptime(date, "%Y-%m-%d").date().isoformat()
        except (TypeError, ValueError):
            pass

        return None

    def __str__(self):
        return '{0} : {1}'.format(self._date, self._rates)

    def check_valid(self, store, txn):
        """
        Verify the validity of the update

        Args:
            store: The local store for bond transactions
            txn: Ignored

        Returns:
            Nothing

        Throws InvalidTransactionError if not valid.
        """
        LOGGER.debug('checking %s', str(self))

        # A LIBOR transaction requires the following:
        # 1. The update must be signed by a well-known key.  Currently this key
        #    has been generated by us, but eventually it is hoped to be the
        #    private counterpart to a public key published by the organization
        #    that provides the LIBORs.
        if self.__libor_object__.Signature is None:
            raise InvalidTransactionError('LIBOR data has not been signed')

        libor_publisher_addr = \
            signing.generate_identifier(self._libor_public_key)

        if not self.__libor_object__.verify_signature(
                libor_publisher_addr):
            raise InvalidTransactionError(
                'Key used to sign LIBOR data does not match publisher')

        # 2. The date must be present, must be in IOS-8601 format, and may not
        #    be a date in the future.
        if self.__libor_object__.date is None:
            raise InvalidTransactionError('Date is not set')

        # Try to convert the date from an ISO-8601 string ("YYYY-MM-DD") to
        # a date object.  An exception indicates that the format is invalid.
        try:
            the_date = \
                datetime.strptime(
                    self.__libor_object__.date,
                    "%Y-%m-%d").date()
        except TypeError:
            raise InvalidTransactionError(
                'Date value <{}> must be a string value'.format(
                    self.__libor_object__.date))
        except ValueError:
            raise InvalidTransactionError(
                'Date <{}> is invalid or not in YYYY-MM-DD format'.format(
                    self.__libor_object__.date))

        if the_date > datetime.utcnow().date():
            raise InvalidTransactionError(
                'Date <{0}> is in the future.  Today is <{1}>.'.format(
                    the_date.isoformat(),
                    datetime.utcnow().date().isoformat()))

        # 3. The data must not already be in the store (i.e., rates have
        #    not already been submitted for this date by some validator).
        if self._object_id in store:
            raise InvalidTransactionError(
                'Rates have already been set for {}'.format(
                    self.__libor_object__.date))

        # 4. Each rate must not be NaN
        for maturity, rate in self.__libor_object__.rates.items():
            if math.isnan(rate):
                raise InvalidTransactionError(
                    '{} maturity does not contain a valid rate'.format(
                        maturity))

    def apply(self, store, txn):
        """
        Add the LIBOR update to the store.  The assumption is that the update
        has already been verified to be valid.

        Args:
            store: The store into which the update is placed.
            txn: Ignored

        Returns:
            Nothing
        """
        LOGGER.debug('apply %s', str(self))

        store[self._object_id] = {
            'object-id': self._object_id,
            'object-type': 'libor',
            'date': self._date,
            'rates': self._rates,
            'signature': self.__libor_object__.Signature
        }

        info = {
            'object-id': 'current_libor',
            'object-type': 'current-libor',
            'date': self._date,
            'rates': self._rates,
            'signature': self.__libor_object__.Signature
        }
        store['current_libor'] = info

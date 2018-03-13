# Copyright 2017 Intel Corporation
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

import threading
import logging
import os
import base64
import binascii

from collections import namedtuple
# pylint: disable=no-name-in-module
from collections.abc import MutableMapping

from sawtooth_validator.database.lmdb_nolock_database \
    import LMDBNoLockDatabase

LOGGER = logging.getLogger(__name__)

PoetKeyState = \
    namedtuple(
        'PoetKeyState',
        ['sealed_signup_data', 'has_been_refreshed', 'signup_nonce'])
""" Instead of creating a full-fledged class, let's use a named tuple for
the PoET key state.  The PoET key state represents the state for a
validator's key that is stored in the PoET key state store.  A PoET key state
object contains:

sealed_signup_data (str): The sealed signup data associated with the
    PoET key.  This must be a byte string containing the base-64 encoded
    sealed signup data.
has_been_refreshed (bool): If this PoET has been used to create the key
    block claim limit number of blocks and a new key pair has been created
    to replace it.
signup_nonce (str): Block ID used at signup time. Used as a time indicator
    to check if this registration attempt has been timed out.
"""


class PoetKeyStateStore(MutableMapping):
    """Manages access to the underlying database holding state associated with
    a PoET public key.  PoetKeyStateStore provides a dict-like interface to
    the PoET key state, mapping a PoET public key to its corresponding state.
    """

    _store_dbs = {}
    _lock = threading.Lock()

    @property
    def poet_public_keys(self):
        """Returns the PoET public keys in the store

        Returns:
            list: The PoET public keys in the store
        """
        return self._store_db.keys()

    @property
    def active_key(self):
        return self._store_db.get('active_key')

    @active_key.setter
    def active_key(self, value):
        # If the value is not None, then we are not going to allow an active
        # key that is not in the key state store.  Setting to None is allowed
        # as that is basically clearing out the active key.
        if value is not None and value not in self._store_db:
            raise \
                ValueError(
                    'Cannot make non-existent key [{}...{}] active'.format(
                        value[:8],
                        value[-8:]))
        self._store_db['active_key'] = value

    def __init__(self, data_dir, validator_id):
        """Initialize the store

        Args:
            data_dir (str): The directory where underlying database file will
                be stored
            validator_id (str): A unique ID for the validator for which the
                store is being created

        Returns:
            None
        """
        with PoetKeyStateStore._lock:
            # Create an underlying LMDB database file for the validator if
            # there already isn't one.  We will create the LMDB with the 'c'
            # flag so that it will open if already exists.
            self._store_db = PoetKeyStateStore._store_dbs.get(validator_id)
            if self._store_db is None:
                db_file_name = \
                    os.path.join(
                        data_dir,
                        'poet-key-state-{}.lmdb'.format(
                            validator_id[:8]))

                LOGGER.debug('Create PoET key state store: %s', db_file_name)

                self._store_db = \
                    LMDBNoLockDatabase(
                        filename=db_file_name,
                        flag='c')
                PoetKeyStateStore._store_dbs[validator_id] = self._store_db

    @staticmethod
    def _check_poet_key_state(poet_key_state):
        try:
            if not isinstance(poet_key_state.sealed_signup_data, str):
                raise ValueError('sealed_signup_data must be a string')
            elif not poet_key_state.sealed_signup_data:
                raise ValueError('sealed_signup_data must not be empty')

            # Although this won't catch everything, verify that the sealed
            # signup data at least decodes successfully
            base64.b64decode(poet_key_state.sealed_signup_data.encode())

            if not isinstance(poet_key_state.has_been_refreshed, bool):
                raise ValueError('has_been_refreshed must be a bool')
            if not isinstance(poet_key_state.signup_nonce, str):
                raise ValueError('signup_nonce {} must be a string'.format(
                    poet_key_state.signup_nonce))
        except (AttributeError, binascii.Error) as error:
            raise ValueError('poet_key_state is invalid: {}'.format(error))

    def __setitem__(self, poet_public_key, poet_key_state):
        """Adds/updates an item in the store

        Args:
            poet_public_key (str): The PoET public key for which key state
                will be stored
            poet_key_state (PoetKeyState): The key state

        Returns:
            None

        Raises:
            ValueError if key state object is not a valid
        """
        PoetKeyStateStore._check_poet_key_state(poet_key_state)
        self._store_db[poet_public_key] = poet_key_state

    def __getitem__(self, poet_public_key):
        """Return the key state corresponding to the PoET public key

        Args:
            poet_public_key (str): The PoET public key for which key state
                will be retrieved

        Returns:
            PoET key state (PoetKeyState)

        Raises:
            KeyError if the PoET public key is not in the store
            ValueError if the key state object is not valid
        """
        # Get the PoET key state from the underlying LMDB.  The only catch is
        # that the data was stored using cbor.dumps().  When this happens, it
        # gets stored as a list not a namedtuple.  When re-creating the poet
        # key state we are going to leverage the namedtuple's _make method.
        try:
            poet_key_state = \
                PoetKeyState._make(self._store_db[poet_public_key])
        except TypeError:  # handle keys persisted using sawtooth v1.0.1
            try:
                old_key_state = self._store_db[poet_public_key]
                old_key_state.append('UNKNOWN_NONCE')
                poet_key_state = PoetKeyState._make(old_key_state)
            except (AttributeError, TypeError) as error:
                raise ValueError('poet_key_state is invalid: {}'.format(error))
        except (AttributeError, ValueError) as error:
            raise ValueError('poet_key_state is invalid: {}'.format(error))

        PoetKeyStateStore._check_poet_key_state(poet_key_state)
        return poet_key_state

    def __delitem__(self, poet_public_key):
        """Remove key state for PoET public key

        Args:
            poet_public_key (str): The PoET public key for which key state
                will be removed

        Returns:
            None
        """
        try:
            del self._store_db[poet_public_key]

            # If the key is the active key, then also clear the active key
            if self.active_key == poet_public_key:
                self.active_key = None
        except KeyError:
            pass

    def __contains__(self, poet_public_key):
        """Determines if key state exists for PoET public key

        Args:
            poet_public_key (str): The PoET public key for which key state
                will be checked

        Returns:
            True if there is key state for PoET public key, False otherwise
        """
        return poet_public_key in self._store_db

    def __iter__(self):
        """Allows for iteration, for example 'for ppk in store:', over PoET
        public keys in store

        Returns:
            iterator
        """
        return iter(self.poet_public_keys)

    def __len__(self):
        """Returns number of PoET public keys in store

        Returns:
            Number of PoET public keys in store
        """
        return len(self._store_db)

    def __str__(self):
        out = []
        for poet_public_key in self:
            poet_key_state = self[poet_public_key]
            out.append(
                '{}...{}: {{SSD: {}...{}, Refreshed: {} nonce:{}}}'.format(
                    poet_public_key[:8],
                    poet_public_key[-8:],
                    poet_key_state.sealed_signup_data[:8],
                    poet_key_state.sealed_signup_data[-8:],
                    poet_key_state.has_been_refreshed,
                    poet_key_state.signup_nonce))

        return ', '.join(out)

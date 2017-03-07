# Copyright 2016, 2017 Intel Corporation
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
import os

from sawtooth_signing import secp256k1_signer as signing


LOGGER = logging.getLogger(__name__)


def load_identity_signing_key(key_dir, key_name):
    """Loads a private key from the key director, based on a validator's
    identity.

    Args:
        key_dir (str): The path to the key directory.
        key_name (str): The name of the key to load.

    Returns:
        str: the private signing key, in hex.
    """
    key_path = os.path.join(key_dir, '{}.wif'.format(key_name))

    if os.path.exists(key_path):
        LOGGER.debug('Found signing key %s', key_path)
        with open(key_path, 'r') as key_file:
            wif_key = key_file.read().strip()
            return signing.encode_privkey(
                signing.decode_privkey(wif_key), 'hex')
    else:
        LOGGER.info('No signing key found. Generating %s', key_path)
        priv_key = signing.generate_privkey()
        with open(key_path, 'w') as key_file:
            key_file.write(signing.encode_privkey(priv_key))

        return signing.encode_privkey(priv_key, 'hex')

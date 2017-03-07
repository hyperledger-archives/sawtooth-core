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
import sys

from sawtooth_signing import secp256k1_signer as signing

from sawtooth_validator.exceptions import LocalConfigurationError

LOGGER = logging.getLogger(__name__)


def load_identity_signing_key(key_dir, key_name):
    """Loads a private key from the key directory, based on a validator's
    identity.

    Args:
        key_dir (str): The path to the key directory.
        key_name (str): The name of the key to load.

    Returns:
        str: the private signing key, in hex.
    """
    key_path = os.path.join(key_dir, '{}.wif'.format(key_name))

    if not os.path.exists(key_path):
        raise LocalConfigurationError(
            "No such signing key file: {}".format(key_path))
    if not os.access(key_path, os.R_OK):
        raise LocalConfigurationError(
            "Key file is not readable: {}".format(key_path))

    LOGGER.info('Loading signing key: %s', key_path)
    try:
        with open(key_path, 'r') as key_file:
            wif_key = key_file.read().strip()
    except IOError as e:
        raise LocalConfigurationError(
            "Could not load key file: {}".format(str(e)))

    try:
        decoded_key = signing.decode_privkey(wif_key)
    except AssertionError:
        # The underlying bitcoin library used by sawtooth_signing asserts to
        # verify correctness of the format.  While we would not normally both
        # log the error and raise an exception, in this case we may need the
        # stacktrace to determine the root cause of the AssertionError, since
        # there is no message provided as part of it.  We log it as debug,
        # while the exception is probably handled by the caller as a fatal
        # startup error.
        LOGGER.debug(
            "AssertionError while decoding wif key", exc_info=sys.exc_info())
        raise LocalConfigurationError(
            "Could not decode key contained in file (AssertionError): "
            "{}".format(key_path))
    return signing.encode_privkey(decoded_key, 'hex')

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

from sawtooth_validator.journal.consensus.poet1.poets_client.poets_client \
    import PoetsClient
from sawtooth_validator.journal.consensus.poet1.poets_client.wait_certificate \
    import WaitCertificate

from sawtooth_validator.journal.consensus.poet1.poets_client.wait_timer \
    import WaitTimer

LOGGER = logging.getLogger(__name__)


"""
Client for PoET Enclave Server.
"""

# pylint: disable=invalid-name
poets_client = None


def initialize(**kwargs):
    # pylint: disable=global-statement
    global poets_client
    poets_client = PoetsClient(**kwargs)


def create_wait_timer(validator_address, previous_certificate_id, local_mean):
    wt = poets_client.create_wait_timer(validator_address,
                                        previous_certificate_id,
                                        local_mean)

    return WaitTimer(wt["Serialized"], wt["Signature"])


def deserialize_wait_timer(ser, sig):
    return WaitTimer(ser, sig)


def create_wait_certificate(wait_timer, block_hash):
    wtr = {
        "Serialized": wait_timer.serialized,
        "Signature": wait_timer.signature
    }
    wc = poets_client.create_wait_certificate(wtr, block_hash)
    if wc:
        return WaitCertificate(wc["Serialized"], wc['Signature'])
    else:
        return None


def deserialize_wait_certificate(ser, sig):
    return WaitCertificate(ser, sig)


def verify_wait_certificate(wait_certificate):
    wait_cert = {
        "Serialized": wait_certificate.serialized,
        "Signature": wait_certificate.signature
    }
    return poets_client.verify_wait_certificate(wait_cert)

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
import time

from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator.common\
    import dict2json
from sawtooth_validator.journal.consensus.poet1.poet_enclave_simulator.common\
    import json2dict

LOGGER = logging.getLogger(__name__)


class EnclaveWaitTimer(object):
    """Represents an enclave-internal representation of a wait timer

    Attributes:
        request_time (float): The request time
        validator_address (str): The address of validator that created
            the wait timer.
        duration (float): The amount of time from request_time when timer
            expires
        previous_certificate_id (str): The id of the previous
            certificate.
        local_mean (float): The local mean wait time based on the
            history of certs
        signature (str): Signature of the timer using PoET private key
            generated during creation of signup info
    """

    @classmethod
    def wait_timer_from_serialized(cls, serialized_timer, signature):
        """
        Takes wait timer that has been serialized to JSON and reconstitutes
        into an EnclaveWaitTimer object.

        Args:
            serialized_timer (str): JSON serialized wait timer
            signature (str): Signature over serialized timer

        Returns:
            An EnclaveWaitTimer object
        """
        deserialized_timer = json2dict(serialized_timer)

        timer = \
            EnclaveWaitTimer(
                validator_address=str(deserialized_timer.get(
                    'validator_address')),
                duration=float(deserialized_timer.get(
                    'duration')),
                previous_certificate_id=str(deserialized_timer.get(
                    'previous_certificate_id')),
                local_mean=float(deserialized_timer.get(
                    'local_mean')),
                signature=signature,
                serialized_timer=serialized_timer)

        timer.request_time = float(deserialized_timer.get('request_time'))

        return timer

    def __init__(self,
                 validator_address,
                 duration,
                 previous_certificate_id,
                 local_mean,
                 signature=None,
                 serialized_timer=None):
        self.request_time = time.time()
        self.validator_address = validator_address
        self.duration = duration
        self.previous_certificate_id = previous_certificate_id
        self.local_mean = local_mean
        self.signature = signature
        self._serialized = serialized_timer
        self._expires = self.request_time + self.duration + 0.1

    def __str__(self):
        return \
            'ENCLAVE_TIMER, {0:0.2f}, {1:0.2f}, {2}'.format(
                self.local_mean,
                self.duration,
                self.previous_certificate_id)

    def serialize(self):
        """
        Serializes to JSON that can later be reconstituted to an
        EnclaveWaitTimer object

        Returns:
            A JSON string representing the serialized version of the object
        """
        if self._serialized is None:
            timer_dict = {
                'request_time': self.request_time,
                'validator_address': self.validator_address,
                'duration': self.duration,
                'previous_certificate_id': self.previous_certificate_id,
                'local_mean': self.local_mean
            }

            self._serialized = dict2json(timer_dict)

        return self._serialized

    def has_expired(self):
        """
        Determines if the wait timer has expired

        Returns:
            True if expired, False otherwise
        """
        return self._expires < time.time()

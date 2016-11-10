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
import json

LOGGER = logging.getLogger(__name__)


class WaitCertificate(object):
    def __init__(self, serialized, signature):
        obj = json.loads(serialized)
        self.block_hash = obj["BlockHash"]
        self.duration = obj["Duration"]
        self._identifier = obj["Identifier"]
        self.local_mean = obj["LocalMean"]
        self.previous_certificate_id = obj["PreviousCertID"]
        self.request_time = obj["RequestTime"]
        self.validator_address = obj["ValidatorAddress"]
        self.serialized = serialized
        self.signature = signature

    def identifier(self):
        return self._identifier

    def serialize(self):
        return self.serialized

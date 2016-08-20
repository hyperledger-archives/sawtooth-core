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

from mktplace.transactions import payment

logger = logging.getLogger(__name__)


class TokenStore(object):
    def __init__(self, creatorid, count=1):
        self.CreatorID = creatorid
        self.Count = count

    def get_tokens(self, count):
        return None


class HoldingStore(TokenStore):
    def __init__(self, creatorid, count, holdingid):
        super(HoldingStore, self).__init__(creatorid, count)

        self.HoldingID = holdingid

    def get_tokens(self, count=None):
        pmt = payment.PayFromHolding()
        pmt.CreatorID = self.CreatorID
        pmt.HoldingID = self.HoldingID
        pmt.Count = count or self.Count
        return pmt

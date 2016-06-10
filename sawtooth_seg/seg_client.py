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

from sawtooth.client import SawtoothClient

from sawtooth_seg.txn_family import SegTransaction
from sawtooth_seg.txn_family import SegTransactionMessage


class SegClient(SawtoothClient):
    def __init__(self,
                 base_url,
                 keyfile=None):
        super(SegClient, self).__init__(
            base_url=base_url,
            store_name='SegTransaction',
            name='SegClient',
            keyfile=keyfile)

    def guess(self, address, balance, block):
        """
        """
        update = {
            'Address': address,
            'Balance': balance,
            'Block': block
        }

        return self.sendtxn(SegTransaction, SegTransactionMessage, update)

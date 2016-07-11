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

import unittest

from ledger.transaction import endpoint_registry
from sawtooth.client import LedgerWebClient


class TestLedgerWebCLient(unittest.TestCase):
    def test_store_url(self):
        lwc = LedgerWebClient("http://localhost:8800")

        self.assertEquals(
            lwc.store_url(endpoint_registry.EndpointRegistryTransaction),
            "http://localhost:8800/store/EndpointRegistryTransaction")

        self.assertEquals(
            lwc.store_url(endpoint_registry.EndpointRegistryTransaction, 't1'),
            "http://localhost:8800/store/EndpointRegistryTransaction/t1")

        self.assertEquals(
            lwc.store_url(endpoint_registry.EndpointRegistryTransaction,
                          blockid='b2'),
            "http://localhost:8800/store/EndpointRegistryTransaction"
            "?blockid=b2")

        self.assertEquals(
            lwc.store_url(endpoint_registry.EndpointRegistryTransaction, 't1',
                          'b2'),
            "http://localhost:8800/store/EndpointRegistryTransaction/t1"
            "?blockid=b2")


if __name__ == '__main__':
    unittest.main()

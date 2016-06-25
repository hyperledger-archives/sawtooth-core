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

from ledger.transaction import endpoint_registry
from txnserver.ledger_web_client import LedgerWebClient


class EndpointRegistryClient(LedgerWebClient):
    def __init__(self, url):
        super(EndpointRegistryClient, self).__init__(url)

    def get_endpoint_list(self, domain='/'):
        endpoints = []

        eplist = self.get_store(
            endpoint_registry.EndpointRegistryTransaction)
        if not eplist:
            return endpoints

        for ep in eplist:
            epinfo = self.get_store(
                endpoint_registry.EndpointRegistryTransaction, ep)
            if epinfo.get('Domain', '/').startswith(domain):
                endpoints.append(epinfo)

        return endpoints

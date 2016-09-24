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

from txnserver.web_pages.base_page import BasePage


LOGGER = logging.getLogger(__name__)


class StatusPage(BasePage):
    def __init__(self, validator):
        BasePage.__init__(self, validator)

    def render_get(self, request, components, msg):
        result = {}
        result['Status'] = self.Validator.status
        result['Name'] = self.Ledger.LocalNode.Name
        result['HttpPort'] = self.Validator.Config.get('HttpPort', None)
        result['Host'] = self.Ledger.LocalNode.NetHost
        result['NodeIdentifier'] = self.Ledger.LocalNode.Identifier
        result['Port'] = self.Ledger.LocalNode.NetPort
        result['Blacklist'] = [x for x in self.Ledger.blacklist]
        result['Peers'] = [
            x.Name for x in self.Ledger.peer_list(allflag=False)
        ]
        result['AllPeers'] = [
            x.Name for x in self.Ledger.peer_list(allflag=True)
        ]
        return result

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

from twisted.web.error import Error
from twisted.web import http

from txnserver.web_pages.base_page import BasePage

from sawtooth.cli.stats_lib.platform_stats import PlatformStats

LOGGER = logging.getLogger(__name__)


class StatisticsPage(BasePage):
    def __init__(self, validator):
        BasePage.__init__(self, validator)
        self.ps = PlatformStats()

    def render_get(self, request, components, args):
        if not components:
            raise Error(http.BAD_REQUEST, 'missing stat family')
        source = components.pop(0)
        result = {}
        if source == 'journal':
            for domain in self.validator.stat_domains.iterkeys():
                result[domain] = self.validator.stat_domains[domain]\
                    .get_stats()
            return result
        if source == 'node':
            for peer in self.validator.gossip.NodeMap.itervalues():
                result[peer.Name] = peer.Stats.get_stats()
                result[peer.Name]['IsPeer'] = peer.is_peer
            return result
        if source == 'platform':
            self.ps.get_stats()
            result['platform'] = self.ps.get_data_as_dict()
            return result
        if source == 'all':
            for domain in self.validator.stat_domains.iterkeys():
                result[domain] = self.validator.stat_domains[domain]\
                    .get_stats()
            for peer in self.validator.gossip.NodeMap.itervalues():
                result[peer.Name] = peer.Stats.get_stats()
                result[peer.Name]['IsPeer'] = peer.is_peer
            self.ps.get_stats()
            result['platform'] = self.ps.get_data_as_dict()
            return result

        if 'journal' in args:
            for domain in self.validator.stat_domains.iterkeys():
                result[domain] = self.validator.stat_domains[domain]\
                    .get_stats()
        if 'node' in args:
            for peer in self.validator.gossip.NodeMap.itervalues():
                result[peer.Name] = peer.Stats.get_stats()
                result[peer.Name]['IsPeer'] = peer.is_peer
        if 'platform' in args:
            self.ps.get_stats()
            result['platform'] = self.ps.get_data_as_dict()
        elif ('journal' not in args) & ('node' not in args) \
                & ('platform' not in args):
            return self._encode_error_response(
                request,
                http.BAD_REQUEST,
                'not valid source or arg')
        return result

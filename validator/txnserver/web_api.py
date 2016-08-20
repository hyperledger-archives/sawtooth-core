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

"""
This module implements the Web server supporting the web api
"""

import logging
import os

from twisted.internet import reactor
from twisted.web.server import Site

from txnserver.config import parse_listen_directives

from txnserver.web_pages.root_page import RootPage

LOGGER = logging.getLogger(__name__)


class ApiSite(Site):
    """
    Override twisted.web.server.Site in order to remove the server header from
    each response.
    """

    def getResourceFor(self, request):
        """
        Remove the server header from the response.
        """
        request.responseHeaders.removeHeader('server')
        return Site.getResourceFor(self, request)


def initialize_web_server(config, validator):
    # Parse the listen directives from the configuration so
    # we know what to bind HTTP protocol to
    listen_directives = parse_listen_directives(config)

    if 'http' in listen_directives:
        static_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "static_content")

        site = ApiSite(RootPage(validator, static_dir))
        interface = listen_directives['http'].host
        if interface is None:
            interface = ''
        LOGGER.info(
            "listen for HTTP requests on (ip='%s', port=%s)",
            interface,
            listen_directives['http'].port)
        reactor.listenTCP(
            listen_directives['http'].port,
            site,
            interface=interface)

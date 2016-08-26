

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
import os

from twisted.web.static import File
from twisted.web.resource import Resource
from twisted.web.resource import NoResource


from txnserver.web_pages.block_page import BlockPage
from txnserver.web_pages.command_page import CommandPage
from txnserver.web_pages.forward_page import ForwardPage
from txnserver.web_pages.prevalidation_page import PrevalidationPage
from txnserver.web_pages.statistics_page import StatisticsPage
from txnserver.web_pages.store_page import StorePage
from txnserver.web_pages.status_page import StatusPage
from txnserver.web_pages.transaction_page import TransactionPage


LOGGER = logging.getLogger(__name__)


class RootPage(Resource):

    def __init__(self, validator, static_dir=None):
        Resource.__init__(self)
        self.validator = validator

        if static_dir is not None and os.path.exists(static_dir):
            for f in os.listdir(static_dir):
                self.putChild(f, File(os.path.join(static_dir, f)))

        self.putChild('block', BlockPage(validator))
        self.putChild('statistics', StatisticsPage(validator))
        self.putChild('store', StorePage(validator))
        self.putChild('status', StatusPage(validator))
        self.putChild('transaction', TransactionPage(validator))

        self.putChild('forward', ForwardPage(validator))
        self.putChild('prevalidation', PrevalidationPage(validator))
        self.putChild('command', CommandPage(validator))

        validator.web_thread_pool.start()

    def getChild(self, name, request):
        out = Resource.getChild(self, name, request)
        LOGGER.warning("%s - %s", request.path, out.__class__.__name__)
        if isinstance(out, NoResource):
            # this matches the pre-existing behavior
            # of accepting any post as a message forward
            components = request.path.split('/')
            while components and components[0] == '':
                components.pop(0)
            LOGGER.warning("%s - %d", components, len(components))
            if len(components) > 0:
                out = ForwardPage(self.validator, components[0])

        return out

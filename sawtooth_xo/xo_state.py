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

from sawtooth_xo.xo_communication import XoCommunication

LOGGER = logging.getLogger(__name__)


class XoState(XoCommunication):
    def __init__(self, baseurl, creator=None):
        super(XoState, self).__init__(baseurl)

        self.CreatorID = creator
        self.State = {}

    def fetch(self, store='XoTransaction'):
        """
        Retrieve the current state from the validator. Rebuild
        the name, type, and id maps for the resulting objects.

        :param str store: optional, the name of the marketplace store to
            retrieve
        """

        LOGGER.debug('fetch state from %s/%s/*', self.BaseURL, store)

        self.State = self.getmsg("/store/{0}/*".format(store))

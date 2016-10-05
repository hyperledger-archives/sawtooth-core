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


LOGGER = logging.getLogger(__name__)


class StorePage(BasePage):
    def __init__(self, validator):
        BasePage.__init__(self, validator)

    def render_get(self, request, components, msg):
        """
        Handle a store request. There are four types of requests:
            empty path -- return a list of known stores
            store name -- return a list of the keys in the store
            store name, key == '*' -- return a complete dump of all keys in the
                store
            store name, key != '*' -- return the data associated with the key
        """
        if not self.journal.GlobalStore:
            raise Error(http.BAD_REQUEST, 'no global store')

        block_id = self.journal.MostRecentCommittedBlockID
        if 'blockid' in msg:
            block_id = msg.get('blockid').pop(0)

        storemap = self.journal.GlobalStoreMap.get_block_store(block_id)
        if not storemap:
            return self._encode_error_response(
                request,
                http.BAD_REQUEST,
                'no store map for block <{0}>'.format(block_id))

        if len(components) == 0:
            return storemap.TransactionStores.keys()

        store_name = '/' + components.pop(0)
        if store_name not in storemap.TransactionStores:
            return self._encode_error_response(
                request,
                http.BAD_REQUEST,
                'no such store <{0}>'.format(store_name))

        store = storemap.get_transaction_store(store_name)

        if len(components) == 0:
            return store.keys()

        key = components[0]
        if key == '*':
            if 'delta' in msg and msg.get('delta').pop(0) == '1':
                return store.dump(True)
            return store.compose()

        if key not in store:
            return self._encode_error_response(
                request,
                http.BAD_REQUEST,
                KeyError('no such key {0}'.format(key)))

        return store[key]

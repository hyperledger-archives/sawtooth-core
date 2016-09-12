

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

from twisted.web import http

from txnserver.web_pages.base_page import BasePage


LOGGER = logging.getLogger(__name__)


class BlockPage(BasePage):
    def __init__(self, validator):
        BasePage.__init__(self, validator)

    def render_get(self, request, components, msg):
        """
        Handle a block request. There are three types of requests:
            empty path -- return a list of the committed block ids
            blockid -- return the contents of the specified block
            blockid and fieldname -- return the specific field within the block

        The request may specify additional parameters:
            blockcount -- the total number of blocks to return (newest to
                oldest)

        Blocks are returned newest to oldest.
        """

        if components and len(components[0]) == 0:
            components.pop(0)

        if len(components) == 0:
            count = 0
            if 'blockcount' in msg:
                count = int(msg.get('blockcount').pop(0))

            block_ids = self.Ledger.committed_block_ids(count)
            return block_ids

        block_id = components.pop(0)
        if block_id not in self.Ledger.BlockStore:
            return self._encode_error_response(
                request,
                http.NOT_FOUND,
                KeyError('unknown block {0}'.format(block_id)))

        binfo = self.Ledger.BlockStore[block_id].dump()
        binfo['Identifier'] = block_id

        if not components:
            return binfo

        field = components.pop(0)
        if field not in binfo:
            return self._encode_error_response(
                request,
                http.NOT_FOUND,
                KeyError('unknown block field {0}'.format(field)))

        return binfo[field]

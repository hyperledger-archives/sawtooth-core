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

        The request may specify additional parameters when path is empty:
            blockcount -- indicates the total number of blocks to return
                (newest to oldest)
            info -- when info equals one, returns block contents and newest
                block id for range of blocks.  When info is in effect, uses
                optional startid, blockcount, and short parameters as follows:
                startid -- starts with specified block id;
                    if startid is not specified, starts with newest block
                blockcount -- indicates number of blocks to return;
                    if blockcount equals zero, returns all blocks
                    if blockcount is not specified, returns one block
                short -- if short equals one or is not specified, then info
                    includes BlockNum and PreviousBlockID
                    if short is not equal to one, then all block content
                    is included

        Blocks are returned newest to oldest.
        """

        if components and len(components[0]) == 0:
            components.pop(0)

        if len(components) == 0:
            if 'info' in msg:
                if int(msg.get('info').pop(0)) is 1:
                    binfo = self.render_info(request, components, msg)
                    return binfo

            count = 0
            if 'blockcount' in msg:
                count = int(msg.get('blockcount').pop(0))

            block_ids = self.journal.committed_block_ids(count)
            return block_ids

        block_id = components.pop(0)
        if block_id not in self.journal.block_store:
            return self._encode_error_response(
                request,
                http.NOT_FOUND,
                KeyError('unknown block {0}'.format(block_id)))

        binfo = self.journal.block_store[block_id].dump()
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

    def render_info(self, request, components, msg):
        GENESIS_PREVIOUS_BLOCK_ID = "0000000000000000"

        if 'startid' in msg:
            block_id = msg.get('startid').pop(0)
            if block_id not in self.journal.block_store:
                return self._encode_error_response(
                    request,
                    http.NOT_FOUND,
                    KeyError('unknown block {0}'.format(block_id)))
        else:
            block_ids = self.journal.committed_block_ids(1)
            if len(block_ids) is 0:
                return self._encode_error_response(
                    request,
                    http.NOT_FOUND,
                    KeyError('no committed blocks available'))
            block_id = block_ids[0]

        count = 1
        if 'blockcount' in msg:
            count = int(msg.get('blockcount').pop(0))
        if count is 0:
            count = self.journal.committed_Block_count

        short = 1
        if 'short' in msg:
            short = 1 if int(msg.get('short').pop(0)) is 1 else 0

        info = {}
        # identify the head (newest) block
        info["head"] = block_id
        info["blocks"] = {}
        for _ in range(0, count):
            binfo = self.journal.block_store[block_id].dump()
            if short is 1:
                info["blocks"][block_id] = \
                    {"PreviousBlockID": binfo["PreviousBlockID"],
                     "BlockNum": binfo["BlockNum"]}
            else:
                info["blocks"][block_id] = binfo
            block_id = binfo["PreviousBlockID"]
            if block_id == GENESIS_PREVIOUS_BLOCK_ID:
                break

        return info

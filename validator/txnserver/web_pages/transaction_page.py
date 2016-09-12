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

from journal import transaction

LOGGER = logging.getLogger(__name__)


class TransactionPage(BasePage):
    def __init__(self, validator):
        BasePage.__init__(self, validator)

    def render_get(self, request, components, msg):
        """
        Handle a transaction request. There are four types of requests:
            empty path -- return a list of the committed transactions ids
            txnid -- return the contents of the specified transaction
            txnid and field name -- return the contents of the specified
                transaction
            txnid and HEAD request -- return success only if the transaction
                                      has been committed
                404 -- transaction does not exist
                302 -- transaction exists but has not been committed
                200 -- transaction has been committed

        The request may specify additional parameters:
            blockcount -- the number of blocks (newest to oldest) from which to
                pull txns

        Transactions are returned from oldest to newest.
        """

        if components and len(components[0]) == 0:
            components.pop(0)

        if len(components) == 0:
            blkcount = 0
            if 'blockcount' in msg:
                blkcount = int(msg.get('blockcount').pop(0))

            txnids = []
            blockids = self.Ledger.committed_block_ids(blkcount)
            while blockids:
                blockid = blockids.pop()
                txnids.extend(self.Ledger.BlockStore[blockid].TransactionIDs)
            return txnids

        txnid = components.pop(0)

        if txnid not in self.Ledger.TransactionStore:
            return self._encode_error_response(
                request,
                http.NOT_FOUND,
                LookupError('no such transaction {0}'.format(txnid)))

        txn = self.Ledger.TransactionStore[txnid]

        test_only = (request.method == 'HEAD')
        if test_only:
            if txn.Status == transaction.Status.committed:
                return None
            else:
                request.setResponseCode(http.FOUND)
                return None

        tinfo = txn.dump()
        tinfo['Identifier'] = txnid
        tinfo['Status'] = txn.Status
        if txn.Status == transaction.Status.committed:
            tinfo['InBlock'] = txn.InBlock

        if not components:
            return tinfo

        field = components.pop(0)
        if field not in tinfo:
            return self._encode_error_response(
                request,
                http.BAD_REQUEST,
                KeyError('unknown transaction field {0}'.format(field)))

        return tinfo[field]

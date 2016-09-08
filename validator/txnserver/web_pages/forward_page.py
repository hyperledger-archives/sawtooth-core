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

import copy
import logging
import traceback

from twisted.web import http
from twisted.web.error import Error

from gossip.common import json2dict
from gossip.common import cbor2dict
from journal import global_store_manager

from sawtooth.exceptions import InvalidTransactionError
from txnserver.web_pages.base_page import BasePage


LOGGER = logging.getLogger(__name__)


class ForwardPage(BasePage):
    isLeaf = True

    def __init__(self, validator, page_name=None):
        BasePage.__init__(self, validator, page_name)

    def render_post(self, request, components, msg):
        """
        Forward a signed message through the gossip network.
        """
        encoding = request.getHeader('Content-Type')
        data = request.content.getvalue()
        try:
            if encoding == 'application/json':
                minfo = json2dict(data)

            elif encoding == 'application/cbor':
                minfo = cbor2dict(data)
            else:
                raise Error("", 'unknown message'
                            ' encoding: {0}'.format(encoding))
            typename = minfo.get('__TYPE__', '**UNSPECIFIED**')
            if typename not in self.Ledger.MessageHandlerMap:
                raise Error("",
                            'received request for unknown message'
                            ' type, {0}'.format(typename))
            msg = self.Ledger.MessageHandlerMap[typename][0](minfo)
        except Error as e:
            LOGGER.info('exception while decoding http request %s; %s',
                        request.path, traceback.format_exc(20))
            raise Error(http.BAD_REQUEST,
                        'unable to decode incoming request: {0}'.format(e))

        if self.Validator.Config.get("LocalValidation", True):
            # determine if the message contains a valid transaction before
            # we send the message to the network

            # we need to start with a copy of the message due to cases
            # where side effects of the validity check may impact objects
            # related to msg
            mymsg = copy.deepcopy(msg)

            if hasattr(mymsg, 'Transaction') and mymsg.Transaction is not None:
                mytxn = mymsg.Transaction
                LOGGER.info('starting local validation '
                            'for txn id: %s type: %s',
                            mytxn.Identifier,
                            mytxn.TransactionTypeName)

                pending_block_txns = None
                if self.Ledger.PendingTransactionBlock is not None:
                    pending_block_txns = \
                        self.Ledger.PendingTransactionBlock.TransactionIDs

                block_id = self.Ledger.MostRecentCommittedBlockID

                real_store_map = \
                    self.Ledger.GlobalStoreMap.get_block_store(block_id)
                temp_store_map = \
                    global_store_manager.BlockStore(real_store_map)
                if not temp_store_map:
                    LOGGER.info('no store map for block %s', block_id)
                    raise Error(http.BAD_REQUEST,
                                'unable to validate enclosed'
                                ' transaction {0}'.format(data))

                pending_txns = copy.copy(self.Ledger.PendingTransactions)
                pending_txn_ids = [x for x in pending_txns.iterkeys()]

                # clone a copy of the ledger's message queue so we can
                # temporarily play forward all locally submitted yet
                # uncommitted transactions
                my_queue = copy.deepcopy(self.Ledger.MessageQueue)

                transaction_type = mytxn.TransactionTypeName
                if transaction_type not in temp_store_map.TransactionStores:
                    LOGGER.info('transaction type %s not in global store map',
                                transaction_type)
                    raise Error(http.BAD_REQUEST,
                                'unable to validate enclosed'
                                ' transaction {0}'.format(data))

                if pending_block_txns is not None:
                    pending_txn_ids = pending_block_txns + pending_txn_ids

                # apply any local pending transactions
                for txn_id in pending_txn_ids:
                    if txn_id in self.Ledger.TransactionStore:
                        pend_txn = self.Ledger.TransactionStore[txn_id]
                        my_store = temp_store_map.get_transaction_store(
                            pend_txn.TransactionTypeName)
                        if pend_txn and pend_txn.is_valid(my_store):
                            my_pend_txn = copy.copy(pend_txn)
                            my_pend_txn.apply(my_store)

                # apply any enqueued messages
                while len(my_queue) > 0:
                    qmsg = my_queue.pop()
                    if qmsg and \
                            qmsg.MessageType in self.Ledger.MessageHandlerMap:
                        if (hasattr(qmsg, 'Transaction') and
                                qmsg.Transaction is not None):
                            my_store = temp_store_map.get_transaction_store(
                                qmsg.Transaction.TransactionTypeName)
                            if qmsg.Transaction.is_valid(my_store):
                                myqtxn = copy.copy(qmsg.Transaction)
                                myqtxn.apply(my_store)

                # determine validity of the POSTed transaction against our
                # new temporary state
                my_store = temp_store_map.get_transaction_store(
                    mytxn.TransactionTypeName)
                try:
                    mytxn.check_valid(my_store)
                except InvalidTransactionError as e:
                    LOGGER.info('submitted transaction fails transaction '
                                'family validation check: %s; %s',
                                request.path, mymsg.dump())
                    raise Error(http.BAD_REQUEST,
                                "InvalidTransactionError: failed transaction "
                                "family validation check: {}".format(str(e)))
                except:
                    LOGGER.info('submitted transaction is '
                                'not valid %s; %s; %s',
                                request.path, mymsg.dump(),
                                traceback.format_exc(20))
                    raise Error(http.BAD_REQUEST,
                                "enclosed transaction is not"
                                " valid {}".format(data))

                LOGGER.info('transaction %s is valid',
                            msg.Transaction.Identifier)

        # and finally execute the associated method
        # and send back the results

        self.Ledger.handle_message(msg)
        return msg

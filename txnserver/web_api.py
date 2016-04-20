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
import traceback
import copy

from twisted.internet import reactor
from twisted.web import http
from twisted.web.error import Error
from twisted.web.resource import Resource
from twisted.web.server import Site

from gossip.common import json2dict
from gossip.common import dict2json
from gossip.common import cbor2dict
from gossip.common import dict2cbor
from gossip.common import pretty_print_dict
from journal import global_store_manager
from journal import transaction
from journal.messages import transaction_message

logger = logging.getLogger(__name__)


class RootPage(Resource):
    isLeaf = True

    def __init__(self, ledger):
        Resource.__init__(self)
        self.Ledger = ledger

        self.GetPageMap = {
            'block': self._handleblkrequest,
            'stat': self._handlestatrequest,
            'store': self._handlestorerequest,
            'transaction': self._handletxnrequest
        }

        self.PostPageMap = {
            'default': self._msgforward,
            'forward': self._msgforward,
            'initiate': self._msginitiate,
            'echo': self._msgecho
        }

    def error_response(self, request, response, *msgargs):
        """
        Generate a common error response for broken requests
        """
        request.setResponseCode(response)

        msg = msgargs[0].format(*msgargs[1:])
        if response > 400:
            logger.warn(msg)
        elif response > 300:
            logger.debug(msg)

        return "" if request.method == 'HEAD' else (msg + '\n')

    def render_GET(self, request):
        """
        Handle a GET request on the HTTP interface. Three paths are accepted:
            /store[/<storename>[/<key>|*]]
            /block[/<blockid>]
            /transaction[/<txnid>]
        """
        # pylint: disable=invalid-name

        # split the request path removing leading duplicate slashes
        components = request.path.split('/')
        while components and components[0] == '':
            components.pop(0)

        prefix = components.pop(0) if components else 'error'

        if prefix not in self.GetPageMap:
            return self.error_response(request, http.BAD_REQUEST,
                                       'unknown request {0}', request.path)

        testonly = (request.method == 'HEAD')

        try:
            response = self.GetPageMap[prefix](components, request.args,
                                               testonly)

            if testonly:
                return ''

            cbor = (request.getHeader('Accept') == 'application/cbor')

            if cbor:
                request.responseHeaders.addRawHeader(b"content-type",
                                                     b"application/cbor")
                return dict2cbor(response)

            request.responseHeaders.addRawHeader(b"content-type",
                                                 b"application/json")

            pretty = 'p' in request.args
            if pretty:
                result = pretty_print_dict(response) + '\n'
            else:
                result = dict2json(response)

            return result

        except Error as e:
            return self.error_response(
                request, int(e.status),
                'exception while processing http request {0}; {1}',
                request.path, str(e))

        except:
            logger.warn('error processing http request %s; %s', request.path,
                        traceback.format_exc(20))
            return self.error_response(request, http.BAD_REQUEST,
                                       'error processing http request {0}',
                                       request.path)

    def render_POST(self, request):
        """
        Handle a POST request on the HTTP interface. All message on the POST
        interface are gossip messages that should be relayed into the gossip
        network as is.
        """
        # pylint: disable=invalid-name

        # break the path into its component parts
        components = request.path.split('/')
        while components and components[0] == '':
            components.pop(0)

        prefix = components.pop(0) if components else 'error'
        if prefix not in self.PostPageMap:
            prefix = 'default'

        # process the message encoding
        encoding = request.getHeader('Content-Type')
        data = request.content.getvalue()

        try:
            if encoding == 'application/json':
                minfo = json2dict(data)
            elif encoding == 'application/cbor':
                minfo = cbor2dict(data)
            else:
                return self.error_response(request, http.BAD_REQUEST,
                                           'unknown message encoding, {0}',
                                           encoding)

            typename = minfo.get('__TYPE__', '**UNSPECIFIED**')
            if typename not in self.Ledger.MessageHandlerMap:
                return self.error_response(
                    request, http.BAD_REQUEST,
                    'received request for unknown message type, {0}', typename)

            msg = self.Ledger.MessageHandlerMap[typename][0](minfo)

        except:
            logger.info('exception while decoding http request %s; %s',
                        request.path, traceback.format_exc(20))
            return self.error_response(
                request, http.BAD_REQUEST,
                'unabled to decode incoming request {0}',
                data)

        # determine if the message contains a valid transaction before
        # we send the message to the network

        # we need to start with a copy of the message due to cases
        # where side effects of the validity check may impact objects
        # related to msg
        mymsg = copy.deepcopy(msg)

        if hasattr(mymsg, 'Transaction') and mymsg.Transaction is not None:
            mytxn = mymsg.Transaction
            logger.info('starting local validation for txn id: %s type: %s',
                        mytxn.Identifier,
                        mytxn.TransactionTypeName)
            blockid = self.Ledger.MostRecentCommittedBlockID

            realstoremap = self.Ledger.GlobalStoreMap.get_block_store(blockid)
            tempstoremap = global_store_manager.BlockStore(realstoremap)
            if not tempstoremap:
                logger.info('no store map for block %s', blockid)
                return self.error_response(
                    request, http.BAD_REQUEST,
                    'unable to validate enclosed transaction {0}',
                    data)

            transtype = mytxn.TransactionTypeName
            if transtype not in tempstoremap.TransactionStores:
                logger.info('transaction type %s not in global store map',
                            transtype)
                return self.error_response(
                    request, http.BAD_REQUEST,
                    'unable to validate enclosed transaction {0}',
                    data)

            # clone a copy of the ledger's message queue so we can
            # temporarily play forward all locally submitted yet
            # uncommitted transactions
            myqueue = copy.copy(self.Ledger.MessageQueue)

            # apply any enqueued messages
            while not myqueue.empty():
                qmsg = myqueue.get()
                if qmsg and qmsg.MessageType in self.Ledger.MessageHandlerMap:
                    if (hasattr(qmsg, 'Transaction') and
                            qmsg.Transaction is not None):
                        mystore = tempstoremap.get_transaction_store(
                            qmsg.Transaction.TransactionTypeName)
                        if qmsg.Transaction.is_valid(mystore):
                            myqtxn = copy.copy(qmsg.Transaction)
                            myqtxn.apply(mystore)
                myqueue.task_done()

            # apply any local pending transactions
            for txnid in self.Ledger.PendingTransactions.iterkeys():
                pendtxn = self.Ledger.TransactionStore[txnid]
                mystore = tempstoremap.get_transaction_store(
                    pendtxn.TransactionTypeName)
                if pendtxn and pendtxn.is_valid(mystore):
                    mypendtxn = copy.copy(pendtxn)
                    logger.debug('applying pending transaction '
                                 '%s to temp store', txnid)
                    mypendtxn.apply(mystore)

            # determine validity of the POSTed transaction against our
            # new temporary state
            mystore = tempstoremap.get_transaction_store(
                mytxn.TransactionTypeName)
            if not mytxn.is_valid(mystore):
                logger.info('submitted transaction is not valid %s; %s',
                            request.path, mymsg.dump())
                return self.error_response(
                    request, http.BAD_REQUEST,
                    'enclosed transaction is not valid {0}',
                    data)
            else:
                logger.info('transaction %s is valid',
                            msg.Transaction.Identifier)

        # and finally execute the associated method and send back the results
        try:
            response = self.PostPageMap[prefix](request, components, msg)

            request.responseHeaders.addRawHeader("content-type", encoding)
            if encoding == 'application/json':
                result = dict2json(response.dump())
            else:
                result = dict2cbor(response.dump())

            return result

        except Error as e:
            return self.error_response(
                request, int(e.status),
                'exception while processing request {0}; {1}', request.path,
                str(e))

        except Exception as e:
            logger.info('caught fall through exception: %s', str(e))
            logger.info('exception while processing http request %s; %s',
                        request.path, traceback.format_exc(20))
            return self.error_response(request, http.BAD_REQUEST,
                                       'error processing http request {0}',
                                       request.path)

    def _msgforward(self, request, components, msg):
        """
        Forward a signed message through the gossip network.
        """

        self.Ledger.handle_message(msg)
        return msg

    def _msginitiate(self, request, components, msg):
        """
        Sign and echo a message
        """

        if request.getClientIP() != '127.0.0.1':
            raise Error(http.NOT_ALLOWED,
                        '{0} not authorized for message initiation'.format(
                            request.getClientIP()))

        if isinstance(msg, transaction_message.TransactionMessage):
            msg.Transaction.sign_from_node(self.Ledger.LocalNode)
        msg.sign_from_node(self.Ledger.LocalNode)

        self.Ledger.handle_message(msg)
        return msg

    def _msgecho(self, request, components, msg):
        """
        Sign and echo a message
        """

        return msg

    def _handlestorerequest(self, pathcomponents, args, testonly):
        """
        Handle a store request. There are four types of requests:
            empty path -- return a list of known stores
            store name -- return a list of the keys in the store
            store name, key == '*' -- return a complete dump of all keys in the
                store
            store name, key != '*' -- return the data associated with the key
        """
        if not self.Ledger.GlobalStore:
            raise Error(http.BAD_REQUEST, 'no global store')

        blockid = self.Ledger.MostRecentCommittedBlockID
        if 'blockid' in args:
            blockid = args.get('blockid').pop(0)

        storemap = self.Ledger.GlobalStoreMap.get_block_store(blockid)
        if not storemap:
            raise Error(http.BAD_REQUEST,
                        'no store map for block <{0}>'.format(blockid))

        if len(pathcomponents) == 0:
            return storemap.TransactionStores.keys()

        storename = '/' + pathcomponents.pop(0)
        if storename not in storemap.TransactionStores:
            raise Error(http.BAD_REQUEST,
                        'no such store <{0}>'.format(storename))

        store = storemap.get_transaction_store(storename)

        if len(pathcomponents) == 0:
            return store.keys()

        key = pathcomponents[0]
        if key == '*':
            if 'delta' in args and args.get('delta').pop(0) == '1':
                return store.dump(True)
            return store.compose()

        if key not in store:
            raise Error(http.BAD_REQUEST, 'no such key {0}'.format(key))

        return store[key]

    def _handleblkrequest(self, pathcomponents, args, testonly):
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

        if not pathcomponents:
            count = 0
            if 'blockcount' in args:
                count = int(args.get('blockcount').pop(0))

            blockids = self.Ledger.committed_block_ids(count)
            return blockids

        blockid = pathcomponents.pop(0)
        if blockid not in self.Ledger.BlockStore:
            raise Error(http.BAD_REQUEST, 'unknown block {0}'.format(blockid))

        binfo = self.Ledger.BlockStore[blockid].dump()
        binfo['Identifier'] = blockid

        if not pathcomponents:
            return binfo

        field = pathcomponents.pop(0)
        if field not in binfo:
            raise Error(http.BAD_REQUEST,
                        'unknown block field {0}'.format(field))

        return binfo[field]

    def _handletxnrequest(self, pathcomponents, args, testonly):
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
        if len(pathcomponents) == 0:
            blkcount = 0
            if 'blockcount' in args:
                blkcount = int(args.get('blockcount').pop(0))

            txnids = []
            blockids = self.Ledger.committed_block_ids(blkcount)
            while blockids:
                blockid = blockids.pop()
                txnids.extend(self.Ledger.BlockStore[blockid].TransactionIDs)
            return txnids

        txnid = pathcomponents.pop(0)

        if txnid not in self.Ledger.TransactionStore:
            raise Error(http.NOT_FOUND,
                        'no such transaction {0}'.format(txnid))

        txn = self.Ledger.TransactionStore[txnid]

        if testonly:
            if txn.Status == transaction.Status.committed:
                return None
            else:
                raise Error(http.FOUND,
                            'transaction not committed {0}'.format(txnid))

        tinfo = txn.dump()
        tinfo['Identifier'] = txnid
        tinfo['Status'] = txn.Status
        if txn.Status == transaction.Status.committed:
            tinfo['InBlock'] = txn.InBlock

        if not pathcomponents:
            return tinfo

        field = pathcomponents.pop(0)
        if field not in tinfo:
            raise Error(http.BAD_REQUEST,
                        'unknown transaction field {0}'.format(field))

        return tinfo[field]

    def _handlestatrequest(self, pathcomponents, args, testonly):
        if not pathcomponents:
            raise Error(http.BAD_REQUEST, 'missing stat family')

        result = dict()

        source = pathcomponents.pop(0)
        if source == 'ledger':
            for domain in self.Ledger.StatDomains.iterkeys():
                result[domain] = self.Ledger.StatDomains[domain].get_stats()
        elif source == 'node':
            for peer in self.Ledger.NodeMap.itervalues():
                result[peer.Name] = peer.Stats.get_stats()
                result[peer.Name]['IsPeer'] = peer.is_peer
        else:
            raise Error(http.NOT_FOUND, 'no stat source specified')

        return result


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


def initialize_web_server(config, ledger):
    if 'HttpPort' in config and config["HttpPort"] > 0:
        root = RootPage(ledger)
        site = ApiSite(root)
        reactor.listenTCP(config["HttpPort"], site)

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
import sys
import urllib
import urllib2
import urlparse

from gossip.common import json2dict, dict2json, cbor2dict, dict2cbor
from journal import transaction

logger = logging.getLogger(__name__)


class MessageException(Exception):
    """
    A class to capture communication exceptions when accessing the validator
    """
    pass


class LedgerWebClient(object):
    GET_HEADER = {"Accept": "application/cbor"}

    def __init__(self, url):
        self.LedgerURL = url
        self.ProxyHandler = urllib2.ProxyHandler({})

    def store_url(self, txntype, key='', blockid='', delta=False):
        """
        store_url -- create a url to access a value store from the ledger

        Args:
            txntype -- type of transaction (or actual transaction), subclass of
                Transaction.Transaction
            key -- index into the transaction store
            blockid - get the state of the store following the validation of
                blockid
        """
        url = self.LedgerURL + '/store' + txntype.TransactionTypeName
        if key:
            url += '/' + key
        url = urlparse.urljoin(url,
                               urlparse.urlparse(url).path.replace('//', '/'))
        url = url.rstrip('/')
        if blockid:
            url += '?blockid={0}'.format(blockid)

        if blockid or delta:
            params = dict()
        if blockid:
            params['blockid'] = blockid
        if delta:
            params['delta'] = '1'
            url += '?' + urllib.urlencode(params)

        return url

    def block_url(self, blockid, field=''):
        """
        block_url -- create a url to access a block from the ledger

        :param id blockid: identifier for the block to retrieve
        :param str field: optional, name of a field to retrieve for the block
        :return: URL for accessing block
        """

        url = self.LedgerURL + '/block/' + blockid
        if field:
            url += '/' + field

        url = urlparse.urljoin(url,
                               urlparse.urlparse(url).path.replace('//', '/'))
        url = url.rstrip('/')

        return url

    def block_list_url(self, count=0):
        """
        block_list_url -- create a url to access a list of block ids

        :param int count: optional, maximum number of blocks to return, 0
            implies all
        :return: URL for accessing block list
        """
        url = self.LedgerURL + '/block'

        url = urlparse.urljoin(url,
                               urlparse.urlparse(url).path.replace('//', '/'))
        url = url.rstrip('/')

        if count:
            url += "?blockcount={0}".format(int(count))

        return url

    def transaction_url(self, txnid, field=''):
        """
        transaction_url -- create a url to access a transaction from the ledger

        :param id txnid: identifier for the transaction to retrieve
        :param str field: optional, name of a field to retrieve for the
            transaction
        :return: URL for accessing transaction
        """

        url = self.LedgerURL + '/transaction/' + txnid
        if field:
            url += '/' + field

        url = urlparse.urljoin(url,
                               urlparse.urlparse(url).path.replace('//', '/'))
        url = url.rstrip('/')

        return url

    def transaction_list_url(self, count=0):
        """
        transaction_list_url -- create a url to access a list of block ids

        :param int count: optional, maximum number of blocks of transactionss
            to return, 0 implies all
        :return: URL for accessing transaction list
        """
        url = self.LedgerURL + '/transaction'

        url = urlparse.urljoin(url,
                               urlparse.urlparse(url).path.replace('//', '/'))
        url = url.rstrip('/')

        if count:
            url += "?blockcount={0}".format(int(count))

        return url

    def message_forward_url(self):
        """
        message_forward_url -- create the url for sending a message to a
        validator, the message will be sent on to the gossip network
        """
        url = self.LedgerURL + '/forward'
        url = urlparse.urljoin(url,
                               urlparse.urlparse(url).path.replace('//', '/'))

        return url

    def message_initiate_url(self):
        """
        message_initiate_url -- create the url for sending an unsigned message
        to a validator that will sign and forward the message
        """
        url = self.LedgerURL + "/initiate"
        url = urlparse.urljoin(url,
                               urlparse.urlparse(url).path.replace('//', '/'))

        return url

    def get_store(self, txntype, key='', blockid='', delta=False):
        """
        Send a request to the ledger web server transaction store and return
        the parsed response, return the value of the specified key within the
        transaction store or a list of valid keys

        Args:
            txntype -- type of the transaction store to contact
            key -- a specific identifier to retrieve
        """
        return self._geturl(self.store_url(txntype, key, blockid, delta))

    def get_block(self, blockid, field=None):
        """
        Send a request to the ledger web server to retrieve data about a
        specific block and return the parsed response,

        :param id blockid: identifier for the block to retrieve
        :param str field: optional, name of a field to retrieve for the block
        :return: dictionary of block data
        """
        return self._geturl(self.block_url(blockid, field))

    def get_block_list(self, count=0):
        """
        Send a request to the ledger web server to retrieve data about a
        specific block and return the parsed response,

        :param int count: optional, maximum number of blocks to return, 0
            implies all
        :return: list of block ids
        """
        return self._geturl(self.block_list_url(count))

    def get_transaction(self, txnid, field=None):
        """
        Send a request to the ledger web server to retrieve data about a
        specific transaction and return the parsed response

        :param id txnid: identifier for the transaction to retrieve
        :param str field: optional, name of a field to retrieve for the
            transaction
        :return: dictionary of transaction data
        """
        return self._geturl(self.transaction_url(txnid, field))

    def get_transaction_status(self, txnid):
        """
        Send a HEAD request to the ledger web server to retrieve the status
        of a specific transaction id.

        :param id txnid: identifier for the transaction to retrieve
        :return: One of the values of :class:`journal.Transaction.status`

        """
        url = self.transaction_url(txnid)

        logger.debug('HEAD content from url <%s>', url)

        try:
            request = urllib2.Request(url)
            request.get_method = lambda: 'HEAD'
            opener = urllib2.build_opener(self.ProxyHandler)
            response = opener.open(request, timeout=30)
            code = response.getcode()
            response.close()
            if code == 200:
                return transaction.Status.committed
            elif code == 302:
                return transaction.Status.pending
            else:
                return transaction.Status.unknown

        except urllib2.HTTPError as err:
            logger.error('peer operation on url %s failed with response: %d',
                         url, err.code)

        except urllib2.URLError as err:
            logger.error('peer operation on url %s failed: %s', url,
                         err.reason)

        except:
            logger.error('no response from peer server for url %s; %s',
                         url, sys.exc_info()[0])

        return transaction.Status.unknown

    def get_transaction_list(self, count=0):
        """
        Send a request to the ledger web server to retrieve a list of
        committed transactions

        :param int count: optional, maximum number of blocks of transactions to
            return, 0 implies all
        :return: list of transaction ids
        """
        return self._geturl(self.transaction_list_url(count))

    def initiate_message(self, msg):
        """
        Post a gossip message to the ledger and return the parsed response,
        generally the response is simply an encoding of the message

        Args:
            msg -- the message to send
        """
        return self._posturl(self.message_initiate_url(), msg.dump())

    def post_message(self, msg):
        """
        Post a gossip message to the ledger and return the parsed response,
        generally the response is simply an encoding of the message

        Args:
            msg -- the message to send
        """
        return self._posturl(self.message_forward_url(), msg.dump())

    def _geturl(self, url):
        """
        Send an HTTP get request to the validator. If the resulting content is
        in JSON or CBOR form, parse it & return the corresponding dictionary.
        """

        logger.debug('get content from url <%s>', url)

        try:
            request = urllib2.Request(url, headers=self.GET_HEADER)
            opener = urllib2.build_opener(self.ProxyHandler)
            response = opener.open(request, timeout=30)

        except urllib2.HTTPError as err:
            logger.error('peer operation on url %s failed with response: %d',
                         url, err.code)
            raise MessageException('operation failed '
                                   'with response: {0}'.format(err.code))

        except urllib2.URLError as err:
            logger.error('peer operation on url %s failed: %s',
                         url, err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except:
            logger.error('no response from peer server for url %s; %s', url,
                         sys.exc_info()[0])
            raise MessageException('no response from server')

        content = response.read()
        headers = response.info()
        response.close()

        encoding = headers.get('Content-Type')

        if encoding == 'application/json':
            return json2dict(content)
        elif encoding == 'application/cbor':
            return cbor2dict(content)
        else:
            return content

    def _posturl(self, url, info, encoding='application/cbor'):
        """
        Post a transaction message to the validator, parse the returning CBOR
        and return the corresponding dictionary.
        """

        if encoding == 'application/json':
            data = dict2json(info)
        elif encoding == 'application/cbor':
            data = dict2cbor(info)
        else:
            logger.error('unknown request encoding %s', encoding)
            return None

        datalen = len(data)

        logger.debug('post transaction to %s with DATALEN=%d, DATA=<%s>', url,
                     datalen, data)

        try:
            request = urllib2.Request(url, data,
                                      {'Content-Type': 'application/cbor',
                                       'Content-Length': datalen})
            opener = urllib2.build_opener(self.ProxyHandler)
            response = opener.open(request, timeout=10)

        except urllib2.HTTPError as err:
            logger.error('peer operation on url %s failed with response: %d',
                         url, err.code)
            raise MessageException('operation failed with resonse: {0}'.format(
                err.code))

        except urllib2.URLError as err:
            logger.error('peer operation on url %s failed: %s', url,
                         err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except NameError as err:
            logger.error('name error %s', err)
            raise MessageException('operation failed: {0}'.format(url))

        except:
            logger.error('no response from peer server for url %s; %s', url,
                         sys.exc_info()[0])
            raise MessageException('no response from server')

        content = response.read()
        headers = response.info()
        response.close()

        encoding = headers.get('Content-Type')

        if encoding == 'application/json':
            value = json2dict(content)
        elif encoding == 'application/cbor':
            value = cbor2dict(content)
        else:
            logger.info('server responds with message %s of unknown type %s',
                        content, encoding)
            value = dict()

        return value

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
import time
import sys
import urllib
import urllib2
import urlparse
from collections import OrderedDict
from enum import Enum

from gossip import node, signed_object
from gossip.common import json2dict, dict2json
from gossip.common import cbor2dict, dict2cbor
from gossip.common import pretty_print_dict
from sawtooth.exceptions import MessageException
from sawtooth.exceptions import ClientException
from journal import transaction


LOGGER = logging.getLogger(__name__)


# Map HTTP status codes to their corresponding transaction status
class TransactionStatus(Enum):
    committed = 200
    pending = 302
    not_found = 404


class _Communication(object):
    """
    A class to encapsulate communication with the validator
    """

    def __init__(self, base_url):
        self._base_url = base_url.rstrip('/')
        self._proxy_handler = urllib2.ProxyHandler({})

    @property
    def base_url(self):
        return self._base_url

    def headrequest(self, path):
        """
        Send an HTTP head request to the validator. Return the result code.
        """
        url = "{0}/{1}".format(self._base_url, path.strip('/'))

        LOGGER.debug('get content from url <%s>', url)

        try:
            request = urllib2.Request(url)
            request.get_method = lambda: 'HEAD'
            opener = urllib2.build_opener(self._proxy_handler)
            response = opener.open(request, timeout=30)

        except urllib2.HTTPError as err:
            # in this case it isn't really an error since we are just looking
            # for the status code
            return err.code

        except urllib2.URLError as err:
            LOGGER.warn('operation failed: %s', err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except:
            LOGGER.warn('no response from server')
            raise MessageException('no response from server')

        return response.code

    def getmsg(self, path):
        """
        Send an HTTP get request to the validator. If the resulting content
        is in JSON form, parse it & return the corresponding dictionary.
        """

        url = "{0}/{1}".format(self._base_url, path.strip('/'))

        LOGGER.debug('get content from url <%s>', url)

        try:
            request = urllib2.Request(url)
            opener = urllib2.build_opener(self._proxy_handler)
            response = opener.open(request, timeout=10)

        except urllib2.HTTPError as err:
            LOGGER.warn('operation failed with response: %s', err.code)
            raise MessageException('operation failed with resonse: {0}'.format(
                err.code))

        except urllib2.URLError as err:
            LOGGER.warn('operation failed: %s', err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except:
            LOGGER.warn('no response from server')
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

    def postmsg(self, msgtype, info):
        """
        Post a transaction message to the validator, parse the returning CBOR
        and return the corresponding dictionary.
        """

        data = dict2cbor(info)
        datalen = len(data)
        url = self._base_url + msgtype

        LOGGER.debug('post transaction to %s with DATALEN=%d, DATA=<%s>', url,
                     datalen, data)

        try:
            request = urllib2.Request(url, data,
                                      {'Content-Type': 'application/cbor',
                                       'Content-Length': datalen})
            opener = urllib2.build_opener(self._proxy_handler)
            response = opener.open(request, timeout=10)

        except urllib2.HTTPError as err:
            LOGGER.warn('operation failed with response: %s', err.code)
            raise MessageException('operation failed with resonse: {0}'.format(
                err.code))

        except urllib2.URLError as err:
            LOGGER.warn('operation failed: %s', err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except:
            LOGGER.warn('no response from server')
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
            LOGGER.info('server responds with message %s of type %s', content,
                        encoding)
            return None

        LOGGER.debug(pretty_print_dict(value))
        return value


class _ClientState(object):
    def __init__(self, base_url, store_name):
        self._communication = _Communication(base_url)
        self._state = {}
        self._base_url = base_url
        self._store_name = store_name

    @property
    def state(self):
        return self._state

    @property
    def base_url(self):
        return self._base_url

    def fetch(self):
        """
        Retrieve the current state from the validator. Rebuild
        the name, type, and id maps for the resulting objects.

        :param str store: optional, the name of the marketplace store to
            retrieve
        """

        LOGGER.debug('fetch state from %s/%s/*',
                     self._base_url,
                     self._store_name)

        self._state = \
            self._communication.getmsg("/store/{0}/*".format(self._store_name))


class SawtoothClient(object):
    def __init__(self,
                 base_url,
                 store_name,
                 name='SawtoothClient',
                 keystring=None,
                 keyfile=None,
                 state=None):
        self._communication = _Communication(base_url)
        self._base_url = base_url
        self._last_transaction = None
        self._local_node = None
        self._current_state = state or _ClientState(base_url, store_name)
        self.fetch_state()

        # Set up the signing key.  Note that if both the keystring and
        # keyfile are not provided, then this is in essence a "read-only"
        # client that may not issue transactions.
        signingkey = None
        if keystring:
            LOGGER.debug("set signing key from string\n%s", keystring)
            signingkey = signed_object.generate_signing_key(wifstr=keystring)
        elif keyfile:
            LOGGER.debug("set signing key from file %s", keyfile)
            try:
                signingkey = signed_object.generate_signing_key(
                    wifstr=open(keyfile, "r").read().strip())
            except IOError as ex:
                raise ClientException(
                    "Failed to load key file: {}".format(str(ex)))

        if signingkey:
            identifier = signed_object.generate_identifier(signingkey)
            self._local_node = node.Node(identifier=identifier,
                                         signingkey=signingkey,
                                         name=name)

    @property
    def base_url(self):
        return self._base_url

    def sendtxn(self, txn_type, txn_msg_type, minfo):
        """
        Build a transaction for the update, wrap it in a message with all
        of the appropriate signatures and post it to the validator
        """

        if self._local_node is None:
            raise ClientException(
                'can not send transactions as a read-only client')

        txn = txn_type(minfo=minfo)

        # add the last transaction submitted to ensure that the ordering
        # in the journal matches the order in which we generated them
        if self._last_transaction:
            txn.Dependencies = [self._last_transaction]

        txn.sign_from_node(self._local_node)
        txnid = txn.Identifier

        txn.check_valid(self._current_state.state)

        msg = txn_msg_type()
        msg.Transaction = txn
        msg.SenderID = self._local_node.Identifier
        msg.sign_from_node(self._local_node)

        try:
            LOGGER.debug('Posting transaction: %s', txnid)
            result = self._communication.postmsg(msg.MessageType, msg.dump())
        except MessageException:
            return None

        # if there was no exception thrown then all transactions should return
        # a value which is a dictionary with the message that was sent
        assert result

        # if the message was successfully posted, then save the transaction
        # id for future dependencies this could be a problem if the transaction
        # fails during application
        self._last_transaction = txnid
        txn.apply(self._current_state.state)

        return txnid

    def fetch_state(self):
        """
        Refresh the state for the client.

        Returns:
            Nothing
        """
        self._current_state.fetch()

    def get_state(self):
        """
        Return the most-recently-cached state for the client.  Note that this
        data may be stale and so it might be desirable to call fetch_state
        first.

        Returns:
            The most-recently-cached state for the client.
        """
        return self._current_state.state

    def get_transaction_status(self, transaction_id):
        """
        Retrieves that status of a transaction.

        Args:
            transaction_id: The ID of the transaction to check.

        Returns:
            One of the TransactionStatus values (committed, etc.)
        """
        return \
            self._communication.headrequest(
                '/transaction/{0}'.format(transaction_id))

    def wait_for_commit(self, txnid=None, timetowait=5, iterations=12):
        """
        Wait until a specified transaction shows up in the ledger's committed
        transaction list

        :param id txnid: the transaction to wait for, the last transaction by
            default
        :param int timetowait: time to wait between polling the ledger
        :param int iterations: number of iterations to wait before giving up
        """

        if not txnid:
            txnid = self._last_transaction
        if not txnid:
            LOGGER.info('no transaction specified for wait')
            return True

        start_time = time.time()
        passes = 0
        while True:
            passes += 1
            status = self.get_transaction_status(txnid)

            if status != TransactionStatus.committed and passes > iterations:
                if status == TransactionStatus.not_found:
                    LOGGER.warn('unknown transaction %s', txnid)
                elif status == TransactionStatus.pending:
                    LOGGER.warn(
                        'transaction %s still uncommitted after %d sec',
                        txnid, int(time.time() - start_time))
                else:
                    LOGGER.warn(
                        'transaction %s returned unexpected status code %d',
                        txnid, status)
                return False

            if status == TransactionStatus.committed:
                return True

            LOGGER.debug('waiting for transaction %s to commit', txnid)
            time.sleep(timetowait)


class LedgerWebClient(object):
    GET_HEADER = {"Accept": "application/cbor"}

    def __init__(self, url):
        self.LedgerURL = url
        self.ProxyHandler = urllib2.ProxyHandler({})

    def status_url(self):
        """
        status_url -- create a url to access a validator's status
        :return: URL for accessing status
        """
        url = self.LedgerURL + '/status'
        url = urlparse.urljoin(url,
                               urlparse.urlparse(url).path.replace('//', '/'))
        url = url.rstrip('/')
        return url

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

    def get_status(self):
        """
        get status of validator
        :return: dictionary of status items
        """
        return self._geturl(self.status_url())

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

        LOGGER.debug('HEAD content from url <%s>', url)

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
            LOGGER.error('peer operation on url %s failed with response: %d',
                         url, err.code)

        except urllib2.URLError as err:
            LOGGER.error('peer operation on url %s failed: %s', url,
                         err.reason)

        except:
            LOGGER.error('no response from peer server for url %s; %s',
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

        LOGGER.debug('get content from url <%s>', url)

        try:
            request = urllib2.Request(url, headers=self.GET_HEADER)
            opener = urllib2.build_opener(self.ProxyHandler)
            response = opener.open(request, timeout=30)

        except urllib2.HTTPError as err:
            LOGGER.error('peer operation on url %s failed with response: %d',
                         url, err.code)
            raise MessageException('operation failed '
                                   'with response: {0}'.format(err.code))

        except urllib2.URLError as err:
            LOGGER.error('peer operation on url %s failed: %s',
                         url, err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except:
            LOGGER.error('no response from peer server for url %s; %s', url,
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
            LOGGER.error('unknown request encoding %s', encoding)
            return None

        datalen = len(data)

        LOGGER.debug('post transaction to %s with DATALEN=%d, DATA=<%s>', url,
                     datalen, data)

        try:
            request = urllib2.Request(url, data,
                                      {'Content-Type': 'application/cbor',
                                       'Content-Length': datalen})
            opener = urllib2.build_opener(self.ProxyHandler)
            response = opener.open(request, timeout=10)

        except urllib2.HTTPError as err:
            LOGGER.error('peer operation on url %s failed with response: %d',
                         url, err.code)
            raise MessageException('operation failed with resonse: {0}'.format(
                err.code))

        except urllib2.URLError as err:
            LOGGER.error('peer operation on url %s failed: %s', url,
                         err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except NameError as err:
            LOGGER.error('name error %s', err)
            raise MessageException('operation failed: {0}'.format(url))

        except:
            LOGGER.error('no response from peer server for url %s; %s', url,
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
            LOGGER.info('server responds with message %s of unknown type %s',
                        content, encoding)
            value = OrderedDict()

        return value

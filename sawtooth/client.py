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
import urllib2

from gossip import node, signed_object
from gossip.common import json2dict, cbor2dict, dict2cbor
from gossip.common import pretty_print_dict

from sawtooth.exceptions import MessageException
from sawtooth.exceptions import ClientException


LOGGER = logging.getLogger(__name__)

# HTTP status codes
HTTP_OK = 200
HTTP_NOT_FOUND = 404


class Communication(object):
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


class ClientState(Communication):
    def __init__(self, base_url, store_name):
        super(ClientState, self).__init__(base_url)

        self._state = {}
        self._store_name = store_name

    @property
    def state(self):
        return self._state

    def fetch(self):
        """
        Retrieve the current state from the validator. Rebuild
        the name, type, and id maps for the resulting objects.

        :param str store: optional, the name of the marketplace store to
            retrieve
        """

        LOGGER.debug('fetch state from %s/%s/*',
                     self.base_url,
                     self._store_name)

        self._state = self.getmsg("/store/{0}/*".format(self._store_name))


class SawtoothClient(Communication):
    def __init__(self,
                 base_url,
                 store_name,
                 name='SawtoothClient',
                 keystring=None,
                 keyfile=None,
                 state=None):
        super(SawtoothClient, self).__init__(base_url)
        self._last_transaction = None

        self._current_state = state or ClientState(base_url, store_name)
        self._current_state.fetch()

        # set up the signing key
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
        else:
            raise TypeError('expecting valid signing key, none provided')

        identifier = signed_object.generate_identifier(signingkey)
        self._local_node = node.Node(identifier=identifier,
                                     signingkey=signingkey,
                                     name=name)

    def sendtxn(self, txn_type, txn_msg_type, minfo):
        """
        Build a transaction for the update, wrap it in a message with all
        of the appropriate signatures and post it to the validator
        """

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
            result = self.postmsg(msg.MessageType, msg.dump())
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

    def get_state(self):
        return self._current_state.state

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

        passes = 0
        while True:
            passes += 1
            status = self.headrequest('/transaction/{0}'.format(txnid))

            if status == HTTP_NOT_FOUND and passes > iterations:
                LOGGER.warn('unknown transaction %s', txnid)
                return False

            if status == HTTP_OK:
                return True

            LOGGER.debug('waiting for transaction %s to commit', txnid)
            time.sleep(timetowait)

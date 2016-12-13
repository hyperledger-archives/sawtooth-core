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
from collections import OrderedDict
import hashlib
import json
import logging
import time
import urllib
import urllib2
import urlparse
try:  # weird windows behavior
    from enum import IntEnum as Enum
except ImportError:
    from enum import Enum

import cbor

from sawtooth.exceptions import ClientException
from sawtooth.exceptions import InvalidTransactionError
from sawtooth.exceptions import MessageException
from sawtooth_signing import pbct_nativerecover as signing


LOGGER = logging.getLogger(__name__)


# Map HTTP status codes to their corresponding transaction status
class TransactionStatus(Enum):
    committed = 200
    pending = 302
    not_found = 404
    internal_server_error = 500,
    server_busy = 503


def _sign_message_with_transaction(transaction, message_type, key):
    """
    Signs a transaction message or transaction
    :param transaction (dict):
    :param key (str): A signing key
    returns message, txnid (tuple): The first 16 characters
    of a sha256 hexdigest.
    """
    transaction['Nonce'] = time.time()
    pub = signing.encode_pubkey(signing.generate_pubkey(key), "hex")
    transaction["PublicKey"] = pub
    sig = signing.sign(_dict2cbor(transaction), key)
    transaction['Signature'] = sig

    txnid = hashlib.sha256(transaction['Signature']).hexdigest()[:16]
    message = {
        'Transaction': transaction,
        '__TYPE__': message_type,
        '__NONCE__': time.time(),
    }
    cbor_serialized_message = _dict2cbor(message)
    signature = signing.sign(cbor_serialized_message, key)
    message['__SIGNATURE__'] = signature
    return message, txnid


def _pretty_print_dict(dictionary):
    """Generates a pretty-print formatted version of the input JSON.

    Args:
        dictionary (dict): the JSON string to format.

    Returns:
        str: pretty-print formatted string.
    """
    return json.dumps(_ascii_encode_dict(dictionary), indent=2, sort_keys=True)


def _json2dict(dictionary):
    """Deserializes JSON into a dictionary.

    Args:
        dictionary (str): the JSON string to deserialize.

    Returns:
        dict: a dictionary object reflecting the structure of the JSON.
    """
    return _ascii_encode_dict(json.loads(dictionary))


def _cbor2dict(dictionary):
    """Deserializes CBOR into a dictionary.

    Args:
        dictionary (bytes): the CBOR object to deserialize.

    Returns:
        dict: a dictionary object reflecting the structure of the CBOR.
    """

    return _ascii_encode_dict(cbor.loads(dictionary))


def _dict2cbor(dictionary):
    """Serializes a dictionary into CBOR.

    Args:
        dictionary (dict): a dictionary object to serialize into CBOR.

    Returns:
        bytes: a CBOR object reflecting the structure of the input dict.
    """

    return cbor.dumps(_unicode_encode_dict(dictionary), sort_keys=True)


def _ascii_encode_dict(item):
    """
    Support method to ensure that JSON is converted to ascii since unicode
    identifiers, in particular, can cause problems
    """
    if isinstance(item, dict):
        return OrderedDict(
            (_ascii_encode_dict(key), _ascii_encode_dict(item[key]))
            for key in sorted(item.keys()))
    elif isinstance(item, list):
        return [_ascii_encode_dict(element) for element in item]
    elif isinstance(item, unicode):
        return item.encode('ascii')
    else:
        return item


def _unicode_encode_dict(item):
    """
    Support method to ensure that JSON is converted to ascii since unicode
    identifiers, in particular, can cause problems
    """
    if isinstance(item, dict):
        return OrderedDict(
            (_unicode_encode_dict(key), _unicode_encode_dict(item[key]))
            for key in sorted(item.keys()))
    elif isinstance(item, list):
        return [_unicode_encode_dict(element) for element in item]
    elif isinstance(item, str):
        return unicode(item)
    else:
        return item


class _Communication(object):
    """
    A class to encapsulate communication with the validator
    """

    def __init__(self, base_url):
        self._base_url = base_url.rstrip('/')
        self._proxy_handler = urllib2.ProxyHandler({})
        self._cookie = None

    @property
    def base_url(self):
        return self._base_url

    def headrequest(self, path):
        """
        Send an HTTP head request to the validator. Return the result code.
        """

        url = urlparse.urljoin(self._base_url, path)

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

    def _print_error_information_from_server(self, err):
        if err.code == 400:
            err_content = err.read()
            LOGGER.warn('Error from server, detail information: %s',
                        err_content)

    def getmsg(self, path, timeout=10):
        """
        Send an HTTP get request to the validator. If the resulting content
        is in JSON form, parse it & return the corresponding dictionary.
        """

        url = urlparse.urljoin(self._base_url, path)

        LOGGER.debug('get content from url <%s>', url)

        try:
            request = urllib2.Request(url)
            opener = urllib2.build_opener(self._proxy_handler)
            response = opener.open(request, timeout=timeout)

        except urllib2.HTTPError as err:
            LOGGER.warn('operation failed with response: %s', err.code)
            self._print_error_information_from_server(err)
            raise MessageException(
                'operation failed with response: {0}'.format(err.code))

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
            return _json2dict(content)
        elif encoding == 'application/cbor':
            return _cbor2dict(content)
        else:
            return content

    def postmsg(self, msgtype_name, info):
        """
        Post a transaction message to the validator, parse the returning CBOR
        and return the corresponding dictionary.
        """

        data = _dict2cbor(info)
        datalen = len(data)
        url = urlparse.urljoin(self._base_url, msgtype_name)

        LOGGER.debug('post transaction to %s with DATALEN=%d, DATA=<%s>', url,
                     datalen, data)

        try:
            request = urllib2.Request(url, data,
                                      {'Content-Type': 'application/cbor',
                                       'Content-Length': datalen})

            if self._cookie:
                request.add_header('cookie', self._cookie)

            opener = urllib2.build_opener(self._proxy_handler)
            response = opener.open(request, timeout=10)
            if not self._cookie:
                self._cookie = response.headers.get('Set-Cookie')
        except urllib2.HTTPError as err:
            content = err.read()
            if content is not None:
                headers = err.info()
                encoding = headers.get('Content-Type')

                if encoding == 'application/json':
                    value = _json2dict(content)
                elif encoding == 'application/cbor':
                    value = _cbor2dict(content)
                else:
                    LOGGER.warn('operation failed with response: %s', err.code)
                    raise MessageException(
                        'operation failed with response: {0}'.format(err.code))
                LOGGER.warn('operation failed with response: %s %s',
                            err.code, str(value))
                if "errorType" in value:
                    if value['errorType'] == "InvalidTransactionError":
                        raise InvalidTransactionError(
                            value['error'] if 'error' in value else value)
                    else:
                        raise MessageException(str(value))
            else:
                raise MessageException(
                    'operation failed with response: {0}'.format(err.code))
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
            value = _json2dict(content)
        elif encoding == 'application/cbor':
            value = _cbor2dict(content)
        else:
            LOGGER.info('server responds with message %s of type %s', content,
                        encoding)
            return None

        LOGGER.debug(_pretty_print_dict(value))
        return value


class UpdateBatch(object):
    """
        Helper object to allow group updates submission using
         sawtooth client.

         the block
          try:
            client.start_batch()
            client.send_txn(...)
            client.send_txn(...)
            client.send_batch()
          except:
            client.reset_batch()

         becomes:

            with UpdateBatch(client) as _:
                client.send_txn()
                client.send_txn()
    """
    def __init__(self, client):
        self.client = client

    def __enter__(self):
        self.client.start_batch()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        if exception_type is None:
            self.client.send_batch()
        else:
            self.client.reset_batch()


class SawtoothClient(object):
    def __init__(self,
                 base_url,
                 store_name=None,
                 name='SawtoothClient',
                 txntype_name=None,
                 msgtype_name=None,
                 keystring=None,
                 keyfile=None,
                 disable_client_validation=False):
        self._base_url = base_url
        self._message_type = msgtype_name
        self._transaction_type = txntype_name

        # an explicit store name takes precedence over a store name
        # implied by the transaction type
        self._store_name = None
        if store_name is not None:
            self._store_name = store_name.strip('/')
        elif txntype_name is not None:
            self._store_name = txntype_name.strip('/')

        self._communication = _Communication(base_url)
        self._last_transaction = None
        self._signing_key = None
        self._identifier = None
        self._update_batch = None
        self._disable_client_validation = disable_client_validation

        if keystring:
            LOGGER.debug("set signing key from string\n%s", keystring)
            self._signing_key = signing.decode_privkey(keystring, 'wif')
        elif keyfile:
            LOGGER.debug("set signing key from file %s", keyfile)
            try:
                self._signing_key = signing.decode_privkey(
                    open(keyfile, "r").read().strip(), 'wif')
            except IOError as ex:
                raise ClientException(
                    "Failed to load key file: {}".format(str(ex)))

        if self._signing_key is not None:
            self._identifier = signing.generate_identifier(
                signing.generate_pubkey(self._signing_key))

    @property
    def base_url(self):
        return self._base_url

    @property
    def last_transaction_id(self):
        return self._last_transaction

    @staticmethod
    def _construct_store_path(txn_type_or_name=None,
                              key=None,
                              block_id=None,
                              delta=False):
        path = 'store'

        path += '/' + txn_type_or_name.strip('/')

        if key is not None:
            path += '/' + key.strip('/')

        query = {}

        if block_id is not None:
            query['blockid'] = block_id
        if delta:
            query['delta'] = '1'
        if len(query) >= 0:
            path += '?' + urllib.urlencode(query)

        return path

    @staticmethod
    def _construct_list_path(list_type, count=None):
        path = list_type

        if count is not None:
            path += '?' + urllib.urlencode({'blockcount': int(count)})

        return path

    @staticmethod
    def _construct_block_list_path(count=0):
        return SawtoothClient._construct_list_path('block', count)

    @staticmethod
    def _construct_transaction_list_path(count=0):
        return SawtoothClient._construct_list_path('transaction', count)

    @staticmethod
    def _construct_item_path(item_type, item_id, field=None):
        path = '{0}/{1}'.format(item_type, item_id)
        if field is not None:
            path += '/' + field

        return path

    @staticmethod
    def _construct_block_path(block_id, field=None):
        return SawtoothClient._construct_item_path('block', block_id, field)

    @staticmethod
    def _construct_transaction_path(transaction_id, field=None):
        return \
            SawtoothClient._construct_item_path(
                'transaction',
                transaction_id,
                field)

    def start_batch(self):
        """
        Start a batch of updates to be sent in a single transaction to
        the validator.

        Returns:
            None

        """
        if self._update_batch is not None:
            raise ClientException(
                "Update batch already in progress.")
        self._update_batch = {
            'Updates': [],
            'Dependencies': []
        }

    def reset_batch(self):
        """
        Abandon the current batch.

        Returns:
            None
        """
        self._update_batch = None

    def send_batch(self):
        """
        Sends the current batch of transactions to the Validator.

        Returns:
            transaction_id of the update transaction

        """
        if len(self._update_batch) == 0:
            raise ClientException("No updates in batch.")
        msg_info = self._update_batch
        self._update_batch = None

        return self.sendtxn(
            minfo=msg_info,
            txntype_name=self._transaction_type,
            msgtype_name=self._message_type)

    def send_update(self, updates, dependencies=None):
        """
        Send an update or list of updates to the validator or add them to an
        existing batch.

        Args:
            updates: single update or list of updates to be sent.
            dependencies: ids of transactions dependencies.

        Returns:
            transaction_id if update is sent, None if it is added to a batch.
        """

        if self._update_batch is not None:
            # if we are in batching mode.
            if isinstance(updates, dict):  # accept single update
                self._update_batch['Updates'].append(updates)
            elif isinstance(updates, (list, tuple)):  # or a list
                self._update_batch['Updates'] += updates
            else:
                raise ClientException(
                    "Unexpected updates type {}.".format(type(updates)))
            if dependencies:
                self._update_batch['Dependencies'] += dependencies
            return None  # there is no transaction id yet.
        else:
            if isinstance(updates, dict):  # accept single update
                updates = [updates]

        dependencies = dependencies or []

        return self.sendtxn(
            minfo={
                'Updates': updates,
                'Dependencies': dependencies,
            },
            txntype_name=self._transaction_type,
            msgtype_name=self._message_type)

    def sendtxn(self, txntype_name, msgtype_name, minfo):
        """
        Build a transaction for the update, wrap it in a message with all
        of the appropriate signatures and post it to the validator. Will
        not work with UpdatesTransaction txn families but will work with
        txn families in Arcade.
        """

        if self._signing_key is None:
            raise ClientException(
                'can not send transactions as a read-only client')

        txn = {'TransactionType': txntype_name}
        txn = dict(txn, **minfo)
        if 'Dependencies' not in txn:
            txn['Dependencies'] = []

        msg, txnid = _sign_message_with_transaction(
            txn,
            msgtype_name,
            self._signing_key)
        try:
            LOGGER.debug('Posting transaction: %s', txnid)
            result = self._communication.postmsg(msgtype_name, msg)
        except MessageException as e:
            LOGGER.warn('Posting transaction failed: %s', str(e))
            return None

        # if there was no exception thrown then all transactions should return
        # a value which is a dictionary with the message that was sent
        assert result

        # if the message was successfully posted, then save the transaction
        # id for future dependencies
        self._last_transaction = txnid
        return txnid

    def get_status(self, timeout=30):
        """
        Get the status for a validator

        Args:
            timeout: Number of seconds to wait for response before determining
                reqeuest has timed out

        Returns: A dictionary of status items
        """
        return self._communication.getmsg('status', timeout)

    def get_store_list(self):
        """
        Get the list of stores on the validator.

        Returns: A list of store names
        """
        return self._communication.getmsg('store')

    def get_store_by_name(self,
                          txn_type_or_name,
                          key=None,
                          block_id=None,
                          delta=False):
        """
        Generic store retrieval method of any named store.  This allows
        complete flexibility in specifying the parameters to the HTTP
        request.

        This function is used when the client has not been configured, on
        construction, to use a specific store or you wish to access a
        different store than the object was initially configured to use.

        This function should only be used when you need absolute control
        over the HTTP request being made to the store.  Otherwise, the
        store convenience methods should be used instead.

        Args:
            txn_type_or_name: A transaction class or object (i.e., derived
                from transaction.Transaction) that can be used to infer the
                store name or a string with the store name.
            key: (optional) The object to retrieve from the store.  If None,
                will returns keys instead of objects.
            block_id: (optional) The block ID to use as ending or starting
                point of retrieval.
            delta: (optional) A flag to indicate of only a delta should be
                returned.  If key is None, this is ignored.

        Returns:
            Either a list of keys, a dictionary of name/value pairs that
            represent one or more objects, or a delta representation of the
            store.

        Notes:
            Reference the Sawtooth Lake Web API documentation for the
            behavior for the key/block_id/delta combinations.
        """
        return \
            self._communication.getmsg(
                self._construct_store_path(
                    txn_type_or_name=txn_type_or_name,
                    key=key,
                    block_id=block_id,
                    delta=delta))

    def get_store(self, key=None, block_id=None, delta=False):
        """
        Generic store retrieval method.  This allows complete flexibility
        in specifying the parameters to the HTTP request.

        This function should only be used when you need absolute control
        over the HTTP request being made to the store.  Otherwise, the
        store convenience methods should be used instead.

        Args:
            key: (optional) The object to retrieve from the store.  If None,
                will returns keys instead of objects.
            block_id: (optional) The block ID to use as ending or starting
                point of retrieval.
            delta: (optional) A flag to indicate of only a delta should be
                returned.  If key is None, this is ignored.

        Returns:
            Either a list of keys, a dictionary of name/value pairs that
            represent one or more objects, or a delta representation of the
            store.

        Notes:
            Reference the Sawtooth Lake Web API documentation for the
            behavior for the key/block_id/delta combinations.

        Raises ClientException if the client object was not created with a
        store name or transaction type.
        """
        if self._store_name is None:
            raise \
                ClientException(
                    'The client must be configured with a store name or '
                    'transaction type')

        return \
            self.get_store_by_name(
                txn_type_or_name=self._store_name,
                key=key,
                block_id=block_id,
                delta=delta)

    def get_store_keys(self):
        """
        Retrieve the list of keys (object IDs) from the store.

        Returns: A list of keys for the store

        Raises ClientException if the client object was not created with a
        store name or transaction type.
        """
        return self.get_store()

    def get_all_store_objects(self):
        """
        Retrieve all of the objects for a particular store

        Returns: A dictionary mapping object keys to objects (dictionaries
            of key/value pairs).

        Raises ClientException if the client object was not created with a
        store name or transaction type.
        """
        return self.get_store(key='*')

    def get_store_object_for_key(self, key):
        """
        Retrieves the object from the store corresponding to the key

        Args:
            key: The object to retrieve from the store

        Returns:
            A dictionary of name/value pairs that represent the object
            associated with the key provided.

        Raises ClientException if the client object was not created with a
        store name or transaction type.
        """
        return self.get_store(key=key)

    def get_store_delta_for_block(self, block_id):
        """
        Retrieves the store for just the block provided.

        Args:
            block_id: The ID of the block for which store should be returned.

        Returns:
             A dictionary that represents the store.

        Raises ClientException if the client object was not created with a
        store name or transaction type.
        """
        return self.get_store(key='*', block_id=block_id, delta=True)

    def get_store_objects_through_block(self, block_id):
        """
        Retrieve all of the objects for a particular store up through the
        block requested.

        Args:
            block_id: The ID of the last block to look for objects.

        Returns: A dictionary mapping object keys to objects (dictionaries
            of key/value pairs).

        Raises ClientException if the client object was not created with a
        store name or transaction type.
        """
        return self.get_store(key='*', block_id=block_id)

    def get_block_list(self, count=None):
        """
        Retrieve the list of block IDs, ordered from newest to oldest.

        Args:
            count: (optional) If not None, specifies the maximum number of
                blocks to return.

        Returns: A list of block IDs.
        """
        return \
            self._communication.getmsg(self._construct_block_list_path(count))

    def get_block(self, block_id, field=None):
        """
        Retrieve information about a specific block, returning all information
        or, if provided, a specific field from the block.

        Args:
            block_id: The ID of the block to retrieve
            field: (optional) If not None, specifies the name of the field to
                retrieve from the block.

        Returns:
            A dictionary of block data, if field is None
            The value for the field, if field is not None
        """
        return \
            self._communication.getmsg(
                self._construct_block_path(block_id, field))

    def get_transaction_list(self, block_count=None):
        """
        Retrieve the list of transaction IDs, ordered from newest to oldest.

        Args:
            block_count: (optional) If not None, specifies the maximum number
                of blocks to return transaction IDs for.

        Returns: A list of transaction IDs.
        """
        return \
            self._communication.getmsg(
                self._construct_transaction_list_path(block_count))

    def get_transaction(self, transaction_id, field=None):
        """
        Retrieve information about a specific transaction, returning all
        information or, if provided, a specific field from the transaction.

        Args:
            transaction_id: The ID of the transaction to retrieve
            field: (optional) If not None, specifies the name of the field to
                retrieve from the transaction.

        Returns:
            A dictionary of transaction data, if field is None
            The value for the field, if field is not None
        """
        return \
            self._communication.getmsg(
                self._construct_transaction_path(transaction_id, field))

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
                self._construct_transaction_path(transaction_id))

    def forward_message(self, msg):
        """
        Post a gossip message to the ledger with the intent of having the
        receiving validator forward it to all of its peers.

        Args:
            msg: The message to send.

        Returns: The parsed response, which is typically the encoding of
            the original message.
        """
        return self._communication.postmsg('forward', msg.dump())

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

            try:
                pretty_status = "{}:{}".format(
                    TransactionStatus(status).name, status)
            except ValueError:
                pretty_status = str(status)

            LOGGER.debug(
                'waiting for transaction %s to commit (%s)',
                txnid,
                pretty_status)
            time.sleep(timetowait)

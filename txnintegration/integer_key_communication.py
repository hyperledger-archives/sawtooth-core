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
A class to canonical communication with the IntegerKey
"""

import logging
import urllib2

from gossip.common import json2dict, cbor2dict, dict2cbor
from gossip.common import pretty_print_dict

logger = logging.getLogger(__name__)


class MessageException(Exception):
    """
    A class to capture communication exceptions when accessing the marketplace
    """
    pass


class IntegerKeyCommunication(object):
    """
    A class to encapsulate communication with the market place servers
    """

    def __init__(self, baseurl):
        self.BaseURL = baseurl.rstrip('/')
        self.ProxyHandler = urllib2.ProxyHandler({})

    def headrequest(self, path):
        """
        Send an HTTP head request to the validator. Return the result code.
        """

        url = "{0}/{1}".format(self.BaseURL, path.strip('/'))

        logger.debug('get content from url <%s>', url)

        try:
            request = urllib2.Request(url)
            request.get_method = lambda: 'HEAD'
            opener = urllib2.build_opener(self.ProxyHandler)
            response = opener.open(request, timeout=30)

        except urllib2.HTTPError as err:
            # in this case it isn't really an error since we are just looking
            # for the status code
            return err.code

        except urllib2.URLError as err:
            logger.warn('operation failed: %s', err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except:
            logger.warn('no response from server')
            raise MessageException('no response from server')

        return response.code

    def getmsg(self, path):
        """
        Send an HTTP get request to the validator. If the resulting content
        is in JSON form, parse it & return the corresponding dictionary.
        """

        url = "{0}/{1}".format(self.BaseURL, path.strip('/'))

        logger.debug('get content from url <%s>', url)

        try:
            request = urllib2.Request(url)
            opener = urllib2.build_opener(self.ProxyHandler)
            response = opener.open(request, timeout=10)

        except urllib2.HTTPError as err:
            logger.warn('operation failed with response: %s', err.code)
            raise MessageException('operation failed with resonse: {0}'.format(
                err.code))

        except urllib2.URLError as err:
            logger.warn('operation failed: %s', err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except:
            logger.warn('no response from server')
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
        url = self.BaseURL + msgtype

        logger.debug('post transaction to %s with DATALEN=%d, DATA=<%s>', url,
                     datalen, data)

        try:
            request = urllib2.Request(url, data,
                                      {'Content-Type': 'application/cbor',
                                       'Content-Length': datalen})
            opener = urllib2.build_opener(self.ProxyHandler)
            response = opener.open(request, timeout=10)

        except urllib2.HTTPError as err:
            logger.warn('operation failed with response: %s', err.code)
            raise MessageException('operation failed with resonse: {0}'.format(
                err.code))

        except urllib2.URLError as err:
            logger.warn('operation failed: %s', err.reason)
            raise MessageException('operation failed: {0}'.format(err.reason))

        except:
            logger.warn('no response from server')
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
            logger.info('server responds with message %s of type %s', content,
                        encoding)
            return None

        logger.debug(pretty_print_dict(value))
        return value

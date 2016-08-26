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

import traceback

from twisted.internet import reactor

from twisted.internet import threads
from twisted.web import http
from twisted.web import server
from twisted.web.error import Error
from twisted.web.resource import Resource

from journal import global_store_manager
from gossip.common import cbor2dict
from gossip.common import json2dict
from gossip.common import dict2json
from gossip.common import dict2cbor
from gossip.common import pretty_print_dict


LOGGER = logging.getLogger(__name__)


class BasePage(Resource):
    isLeaf = True

    def __init__(self, validator, page_name=None):
        Resource.__init__(self)
        self.Ledger = validator.Ledger
        self.Validator = validator
        self.thread_pool = validator.web_thread_pool
        self.max_workers = self.Validator.Config.get("MaxWebWorkers", 7)
        if page_name is None:
            self.page_name = self.__class__.__name__.lower()
            loc = self.page_name.find("page")
            if loc != -1:
                self.page_name = self.page_name[:loc]
        else:
            self.page_name = page_name

    def error_response(self, request, response, *msgargs):
        """
        Generate a common error response for broken requests
        """
        request.setResponseCode(response)

        msg = msgargs[0].format(*msgargs[1:])
        if response > 400:
            LOGGER.warn(msg)
        elif response > 300:
            LOGGER.debug(msg)

        return "" if request.method == 'HEAD' else (msg + '\n')

    def error_callback(self, failure, request):
        LOGGER.error("Error processing: %s %s %s",
                     request,
                     failure.getErrorMessage(),
                     failure.getTraceback())
        request.processingFailed(failure)
        return None

    def render_get(self, request, components, msg):
        self.error_response(request, http.NOT_FOUND, "")

    def do_get(self, request):
        """
        Handle a GET request on the HTTP interface. Three paths are accepted:
            /store[/<storename>[/<key>|*]]
            /block[/<blockid>]
            /transaction[/<txnid>]
        """
        # pylint: disable=invalid-name

        # split the request path removing leading duplicate slashes
        LOGGER.info("%s.do_get %s", self.__class__.__name__, request.path)
        components = request.path.split('/')
        while components and components[0] == '':
            components.pop(0)

        if components[0] != self.page_name:
            return self.error_response(
                request,
                http.NOT_FOUND,
                "Invalid page name: {}", request.path)
        else:
            components.pop(0)

        test_only = (request.method == 'HEAD')
        try:
            response = self.render_get(request, components, request.args)
            if test_only:
                return ''

            cbor = (request.getHeader('Accept') == 'application/cbor')

            if cbor:
                request.responseHeaders.addRawHeader(b"content-type",
                                                     b"application/cbor")
                return dict2cbor(response)

            request.responseHeaders.addRawHeader(b"content-type",
                                                 b"application/json")
            pretty = False
            if 'p' in request.args:
                pretty = request.args['p'] == ['1']

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
            LOGGER.warn('error processing http request %s; %s', request.path,
                        traceback.format_exc(20))
            return self.error_response(request, http.BAD_REQUEST,
                                       'error processing http request {0}',
                                       request.path)

    def render_post(self, request, components, msg):
        self.error_response(request, http.NOT_FOUND, "")

    def _get_message(self, request):
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
            return self.Ledger.MessageHandlerMap[typename][0](minfo)
        except Error as e:
            LOGGER.info('exception while decoding http request %s; %s',
                        request.path, traceback.format_exc(20))
            raise Error(http.BAD_REQUEST,
                        'unable to decode incoming request: {0}'.format(e))

    def _get_store_map(self):
        block_id = self.Ledger.MostRecentCommittedBlockID
        real_store_map = \
            self.Ledger.GlobalStoreMap.get_block_store(block_id)
        temp_store_map = \
            global_store_manager.BlockStore(real_store_map)
        if not temp_store_map:
            LOGGER.info('no store map for block %s', block_id)
            raise Error(http.BAD_REQUEST, 'no store map for block {0} ',
                        block_id)
        return temp_store_map

    def do_post(self, request):
        """
        Handle two types of HTTP POST requests:
         - gossip messages.  relayed to the gossip network as is
         - validator command and control (/command)
        """

        # break the path into its component parts
        components = request.path.split('/')
        while components and components[0] == '':
            components.pop(0)

        try:
            response = self.render_post(request, components, request.args)

            encoding = request.getHeader('Content-Type')
            request.responseHeaders.addRawHeader("content-type", encoding)
            if encoding == 'application/json':
                result = dict2json(response.dump())
            else:
                result = dict2cbor(response.dump())

            return result

        except Error as e:
            return self.error_response(
                request, int(e.status),
                'exception while processing request {0}; {1}',
                request.path, str(e))

        except:
            LOGGER.info('exception while processing http request %s; %s',
                        request.path, traceback.format_exc(20))
            return self.error_response(request, http.BAD_REQUEST,
                                       'error processing http request {0}',
                                       request.path)

    def final(self, message, request):
        request.write(message)
        try:
            request.finish()
        except RuntimeError:
            LOGGER.error("No connection when request.finish called")

    def render_GET(self, request):
        # pylint: disable=invalid-name
        if len(self.thread_pool.working) > self.max_workers:
            return self.error_response(
                request, http.SERVICE_UNAVAILABLE,
                'Service is unavailable at this time, Please try again later')
        else:
            d = threads.deferToThreadPool(reactor, self.thread_pool,
                                          self.do_get, request)
            d.addCallback(self.final, request)
            d.addErrback(self.error_callback, request)
            return server.NOT_DONE_YET

    def render_POST(self, request):
        # pylint: disable=invalid-name
        if len(self.thread_pool.working) > self.max_workers:
            return self.error_response(
                request, http.SERVICE_UNAVAILABLE,
                'Service is unavailable at this time, Please try again later')
        else:
            d = threads.deferToThreadPool(reactor, self.thread_pool,
                                          self.do_post, request)
            d.addCallback(self.final, request)
            d.addErrback(self.error_callback, request)
            return server.NOT_DONE_YET

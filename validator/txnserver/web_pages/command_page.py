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

from twisted.web import http
from twisted.web.error import Error

from gossip.common import json2dict
from gossip.common import dict2json
from txnserver.web_pages.base_page import BasePage

LOGGER = logging.getLogger(__name__)


class CommandPage(BasePage):
    def __init__(self, validator):
        BasePage.__init__(self, validator)

    def render_post(self, request, components, msg):
        """
        Process validator control commands
        """
        encoding = request.getHeader('Content-Type')
        data = request.content.getvalue()

        try:
            if encoding == 'application/json':
                minfo = json2dict(data)
            else:
                raise Error("", 'unknown message'
                            ' encoding: {0}'.format(encoding))
        except Error as e:
            LOGGER.info('exception while decoding http request %s; %s',
                        request.path, traceback.format_exc(20))
            return self._encode_error_response(
                request,
                http.BAD_REQUEST,
                'unable to decode incoming request {0}'.format(str(e)))

        # process /command
        try:
            if minfo['action'] == 'start':
                if self.validator.delaystart is True:
                    self.validator.delaystart = False
                    LOGGER.info("command received : %s", minfo['action'])
                    minfo['action'] = 'started'
                else:
                    LOGGER.warn("validator startup not delayed")
                    minfo['action'] = 'running'
            else:
                LOGGER.warn("unknown command received")
                minfo['action'] = 'startup failed'

            request.responseHeaders.addRawHeader("content-type", encoding)
            result = dict2json(minfo)
            return result
        except Error as e:
            raise Error(int(e.status),
                        'exception while processing'
                        ' request {0}; {1}'.format(request.path, str(e)))

        except:
            LOGGER.info('exception while processing http request %s; %s',
                        request.path, traceback.format_exc(20))
            raise

        return msg

# Copyright 2017 Intel Corporation
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

import unittest
import logging
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from base64 import b64encode

from sawtooth_integration.tests.integration_tools import wait_until_status


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class TestBasicAuth(unittest.TestCase):

    def setUp(self):
        wait_until_status('http://basic_auth_proxy/sawtooth', status_code=401)

    def test_fetch_blocks(self):
        """Checks that an authenticated request can be made through a proxy
        to the REST API, and that the returned "link" parameter properly
        reflects the url of the proxy.

        The proxy should redirect from `http://basic_auth_proxy/sawtooth` to
        `http://rest_api:8080`, and be configured with a Basic Auth
        username:password combination of 'sawtooth:sawtooth'.

        In order to get back the correct link, the proxy must both forward the
        host and add a custom RequestHeader of 'X-Forwarded-Path: /sawtooth'.
        """
        url = 'http://basic_auth_proxy/sawtooth/blocks'
        auth = 'Basic {}'.format(b64encode(b'sawtooth:sawtooth').decode())
        LOGGER.info(('\n'
                     'Sending request to "{}",\n'
                     'with "Authorition: {}"').format(url, auth))

        try:
            response = urlopen(Request(url, headers={'Authorization': auth}))
        except HTTPError as e:
            response = e.file
            error = json.loads(response.read().decode())['error']
            LOGGER.error('{} - {}:'.format(error['code'], error['title']))
            LOGGER.error(error['message'])

        self.assertEqual(200, response.getcode())
        LOGGER.info('Authorization succeeded, 200 response received.')

        link = json.loads(response.read().decode())['link']

        LOGGER.info('Verifying link: "{:.50}..."'.format(link))
        self.assertTrue(link.startswith(url))
        LOGGER.info('Link verified.')

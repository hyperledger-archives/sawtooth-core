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

# pylint: disable=protected-access

import unittest
import logging
import ssl
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from base64 import b64encode

from sawtooth_integration.tests.integration_tools import wait_until_status


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class TestBasicAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wait_until_status('http://rest-api:8008/blocks', status_code=200)
        wait_until_status('http://basic_auth_proxy/sawtooth', status_code=401)

    def test_http_basic_auth(self):
        """Checks that a Basic Auth request can be made with unencrypted HTTP.
        """
        url = 'http://basic_auth_proxy/sawtooth/blocks'
        self._assert_valid_authed_request(url)

    def test_ssl_basic_auth(self):
        """Checks that a Basic Auth request can be made with encrypted HTTPS.
        """
        url = 'https://basic_auth_proxy/sawtooth/blocks'
        self._assert_valid_authed_request(url)

    def _assert_valid_authed_request(self, url):
        """Asserts that a Basic Auth request was made successfully through a
        proxy to the REST API, and that the returned "link" parameter properly
        reflects the url of the proxy.

        The proxy should redirect from the passed url's domain to
        `http://rest-api:8008`, and be configured with a Basic Auth
        username:password combination of 'sawtooth:sawtooth'.

        In order to get back the correct link, the proxy must both forward the
        host and add a custom RequestHeader of 'X-Forwarded-Path: /sawtooth'.
        """
        auth = 'Basic {}'.format(b64encode(b'sawtooth:sawtooth').decode())
        LOGGER.info(('\n'
                     'Sending request to "%s",\n'
                     'with "Authorization: %s"'), url, auth)

        request = Request(url, headers={'Authorization': auth})
        context = ssl._create_unverified_context()

        try:
            response = urlopen(request, context=context)
        except HTTPError as e:
            LOGGER.error('An error occured while requesting "%s"', url)

            try:
                error = json.loads(e.file.read().decode())['error']
                fail_msg = 'REST API Error: {} - {}:'.format(
                    error['code'], error['title'])
            except json.decoder.JSONDecodeError:
                fail_msg = 'HTTP Error: {} - {}'.format(e.code, e.msg)

            self.fail(fail_msg)

        self.assertEqual(200, response.getcode())
        LOGGER.info('Authorization succeeded, 200 response received.')

        link = json.loads(response.read().decode())['link']

        LOGGER.info('Verifying link: "%s"', link)
        self.assertTrue(link.startswith(url))
        LOGGER.info('Link verified.')

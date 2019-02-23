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
import json
from urllib.error import HTTPError
from requests.auth import HTTPDigestAuth
import requests

from sawtooth_integration.tests.integration_tools import wait_until_status


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class TestDigestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wait_until_status('http://rest-api:8008/blocks', status_code=200)
        wait_until_status('http://digest-auth-proxy/sawtooth', status_code=401)

    def test_http_digest_auth(self):
        """Checks that a Digest Auth request can be made with unencrypted HTTP.
        """
        url = 'http://digest-auth-proxy/sawtooth/blocks'
        self._assert_valid_authed_request(url)

    def test_ssl_digest_auth(self):
        """Checks that a Digest Auth request can be made with encrypted HTTPS.
        """
        url = 'https://digest-auth-proxy/sawtooth/blocks'
        self._assert_valid_authed_request(url)

    def _assert_valid_authed_request(self, url):
        """Asserts that a Digest Auth request was made successfully through a
        proxy to the REST API, and that the returned "link" parameter properly
        reflects the url of the proxy.

        The proxy should redirect from the passed url's domain to
        `http://rest-api:8008`, and be configured with a Digest Auth
        username:password combination of 'sawtooth:sawtooth'.

        In order to get back the correct link, the proxy must both forward the
        host and add a custom RequestHeader of 'X-Forwarded-Path: /sawtooth'.
        """
        user = 'sawtooth'
        pw = 'sawtooth'

        try:
            response = requests.get(url, auth=HTTPDigestAuth(user, pw),
                                    verify=False)
        except HTTPError as e:
            LOGGER.error('An error occured while requesting "%s"', url)

            try:
                error = json.loads(e.file.read().decode())['error']
                fail_msg = 'REST API Error: {} - {}:'.format(
                    error['code'], error['title'])
            except json.decoder.JSONDecodeError:
                fail_msg = 'HTTP Error: {} - {}'.format(e.code, e.msg)

            self.fail(fail_msg)

        self.assertEqual(200, response.status_code)
        LOGGER.info('Authorization succeeded, 200 response received.')

        link = json.loads(response.text)['link']

        LOGGER.info('Verifying link: "%s"', link)
        self.assertTrue(link.startswith(url))
        LOGGER.info('Link verified.')

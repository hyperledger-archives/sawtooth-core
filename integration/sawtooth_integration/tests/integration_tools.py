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

import hashlib
import json
import logging
import os
import time
from base64 import b64decode
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.error import URLError
from http.client import RemoteDisconnected
import requests

LOGGER = logging.getLogger(__name__)

WAIT = 300


class RestClient:
    def __init__(self, url, namespace=None):
        self.url = url
        self.namespace = namespace

    def get_leaf(self, address, head=None):
        query = self._get('/state/' + address, head=head)
        return b64decode(query['data'])

    def list_state(self, namespace=None, head=None):
        namespace = self.namespace if namespace is None else namespace

        return self._get('/state', address=namespace, head=head)

    def get_data(self, namespace=None, head=None):
        namespace = self.namespace if namespace is None else namespace

        return [
            b64decode(entry['data'])
            for entry in self.list_state(
                namespace=namespace,
                head=head,
            )['data']
        ]

    def send_batches(self, batch_list):
        """Sends a list of batches to the validator.

        Args:
            batch_list (:obj:`BatchList`): the list of batches

        Returns:
            dict: the json result data, as a dict
        """
        submit_response = self._post('/batches', batch_list)
        return self._submit_request("{}&wait={}".format(
            submit_response['link'], WAIT))

    def block_list(self):
        return self._get('/blocks')

    def _get(self, path, **queries):
        code, json_result = self._submit_request(
            self.url + path,
            params=self._format_queries(queries),
        )

        # concat any additional pages of data
        while code == 200 and 'next' in json_result.get('paging', {}):
            previous_data = json_result.get('data', [])
            code, json_result = self._submit_request(
                json_result['paging']['next'])
            json_result['data'] = previous_data + json_result.get('data', [])

        if code == 200:
            return json_result
        if code == 404:
            raise Exception(
                'There is no resource with the identifier "{}"'.format(
                    path.split('/')[-1]))

        raise Exception("({}): {}".format(code, json_result))

    def _post(self, path, data, **queries):
        if isinstance(data, bytes):
            headers = {'Content-Type': 'application/octet-stream'}
        else:
            data = json.dumps(data).encode()
            headers = {'Content-Type': 'application/json'}
        headers['Content-Length'] = '%d' % len(data)

        code, json_result = self._submit_request(
            self.url + path,
            params=self._format_queries(queries),
            data=data,
            headers=headers,
            method='POST')

        if code in (200, 201, 202):
            return json_result

        raise Exception("({}): {}".format(code, json_result))

    def _submit_request(self, url, params=None, data=None,
                        headers=None, method="GET"):
        """Submits the given request, and handles the errors appropriately.

        Args:
            url (str): the request to send.
            params (dict): params to be passed along to get/post
            data (bytes): the data to include in the request.
            headers (dict): the headers to include in the request.
            method (str): the method to use for the request, "POST" or "GET".

        Returns:
            tuple of (int, str): The response status code and the json parsed
                body, or the error message.

        Raises:
            `Exception`: If any issues occur with the URL.
        """
        try:
            if method == 'POST':
                result = requests.post(
                    url, params=params, data=data, headers=headers)
            elif method == 'GET':
                result = requests.get(
                    url, params=params, data=data, headers=headers)
            result.raise_for_status()
            return (result.status_code, result.json())
        except requests.exceptions.HTTPError as excp:
            return (excp.response.status_code, excp.response.reason)
        except RemoteDisconnected as excp:
            raise Exception(excp)
        except requests.exceptions.ConnectionError as excp:
            raise Exception(
                ('Unable to connect to "{}": '
                 'make sure URL is correct').format(self.url))

    @staticmethod
    def _format_queries(queries):
        queries = {k: v for k, v in queries.items() if v is not None}
        return queries if queries else ''


class XoClient(RestClient):
    def __init__(self, url):
        super().__init__(
            url=url,
            namespace='5b7349')

    def decode_data(self, data):
        return {
            name: (board, state, player_1, player_2)
            for name, board, state, player_1, player_2 in [
                game.split(',')
                for game in data.decode().split('|')
            ]
        }

    def make_xo_address(self, name):
        return self.namespace + hashlib.sha512(name.encode()).hexdigest()[0:64]

    def get_game(self, name):
        return self.decode_data(
            self.get_leaf(
                self.make_xo_address(name)))[name]


def wait_until_status(url, status_code=200):
    """Pause the program until the given url returns the required status.

    Args:
        url (str): The url to query.
        status_code (int, optional): The required status code. Defaults to 200.
    """
    sleep_time = 1
    while True:
        try:
            response = urlopen(url)
            if response.getcode() == status_code:
                return

        except HTTPError as err:
            if err.code == status_code:
                return

            LOGGER.debug('failed to read url: %s', str(err))
        except URLError as err:
            LOGGER.debug('failed to read url: %s', str(err))

        LOGGER.debug('Retrying in %s secs', sleep_time)
        time.sleep(sleep_time)


def wait_for_rest_apis(endpoints):
    """Pause the program until all the given REST API endpoints are available.

    Args:
        endpoints (list of str): A list of host:port strings.
    """
    for endpoint in endpoints:
        http = 'http://'
        url = endpoint if endpoint.startswith(http) else http + endpoint
        wait_until_status(
            '{}/blocks'.format(url),
            status_code=200)


class SetSawtoothHome:
    def __init__(self, sawtooth_home):
        self._sawtooth_home = sawtooth_home

    def __enter__(self):
        os.environ['SAWTOOTH_HOME'] = self._sawtooth_home
        for directory in map(lambda x: os.path.join(self._sawtooth_home, x),
                             ['data', 'keys', 'etc', 'policy', 'logs']):
            if not os.path.exists(directory):
                os.mkdir(directory)

    def __exit__(self, exc_type, exc_val, exc_tb):
        del os.environ['SAWTOOTH_HOME']

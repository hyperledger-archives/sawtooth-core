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

import json
import urllib.request as urllib
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError

from sawtooth_cli.exceptions import CliException


class RestClient(object):
    def __init__(self, base_url=None):
        self._base_url = base_url or 'http://localhost:8080'

    def list_blocks(self):
        return self._get('/blocks')['data']

    def get_block(self, block_id):
        safe_id = urllib.quote(block_id, safe='')
        return self._get('/blocks/' + safe_id)['data']

    def list_batches(self):
        return self._get('/batches')['data']

    def get_batch(self, batch_id):
        safe_id = urllib.quote(batch_id, safe='')
        return self._get('/batches/' + safe_id)['data']

    def list_state(self, subtree=None, head=None):
        return self._get('/state', address=subtree, head=head)

    def get_leaf(self, address, head=None):
        return self._get('/state/' + address, head=head)

    def get_statuses(self, batch_ids, wait=None):
        """Fetches the committed status for a list of batch ids.

        Args:
            batch_ids (list of str): The ids to get the status of.
            wait (optional, int): Indicates that the api should wait to
                respond until the batches are committed or the specified
                time in seconds has elapsed.

        Returns:
            dict: A statuses map, with ids as keys, and statuses values
        """
        return self._post('/batch_status', batch_ids, wait=wait)['data']

    def send_batches(self, batch_list):
        """Sends a list of batches to the validator.

        Args:
            batch_list (:obj:`BatchList`): the list of batches

        Returns:
            dict: the json result data, as a dict
        """
        return self._post('/batches', batch_list.SerializeToString())

    def _get(self, path, **queries):
        code, json_result = self._submit_request(
            self._base_url + path + self._format_queries(queries))
        if code == 200:
            return json_result
        elif code == 404:
            return None
        else:
            raise CliException("({}): {}".format(code, json_result))

    def _post(self, path, data, **queries):
        if isinstance(data, bytes):
            headers = {'Content-Type': 'application/octet-stream'}
        else:
            data = json.dumps(data).encode()
            headers = {'Content-Type': 'application/json'}
        headers['Content-Length'] = '%d' % len(data)

        request = urllib.Request(
            self._base_url + path + self._format_queries(queries),
            data,
            headers=headers,
            method='POST')

        code, json_result = self._submit_request(request)
        if code == 200 or code == 201 or code == 202:
            return json_result
        else:
            raise CliException("({}): {}".format(code, json_result))

    def _submit_request(self, url_or_request):
        """Submits the given request, and handles the errors appropriately.

        Args:
            url_or_request (str or `urlib.request.Request`): the request to
                send.

        Returns:
            tuple of (int, str): The response status code and the json parsed
                body, or the error message.

        Raises:
            `CliException`: If any issues occur with the URL.
        """
        try:
            result = urllib.urlopen(url_or_request)
            return (result.status, json.loads(result.read().decode()))
        except HTTPError as e:
            return (e.code, e.msg)
        except URLError as e:
            raise CliException(
                ('Unable to connect to "{}": '
                 'make sure URL is correct').format(self._base_url))

    @staticmethod
    def _format_queries(queries):
        queries = {k: v for k, v in queries.items() if v is not None}
        return '?' + urlencode(queries) if queries else ''

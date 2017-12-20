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
import urllib.request
import urllib.error
import base64
import time

from sawtooth_block_info.common import CONFIG_ADDRESS
from sawtooth_block_info.common import create_block_address
from sawtooth_block_info.protobuf.block_info_pb2 import BlockInfoConfig
from sawtooth_block_info.protobuf.block_info_pb2 import BlockInfo

from sawtooth_intkey.intkey_message_factory import IntkeyMessageFactory


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def get_blocks():
    response = query_rest_api('/blocks')
    return response['data']


def get_block_info_config():
    bic = BlockInfoConfig()
    bic.ParseFromString(get_state(CONFIG_ADDRESS))
    return bic


def get_block_info(block_num):
    bi = BlockInfo()
    bi.ParseFromString(get_state(create_block_address(block_num)))
    return bi


def get_state(address):
    response = query_rest_api('/state/%s' % address)
    return base64.b64decode(response['data'])


def post_batch(batch):
    headers = {'Content-Type': 'application/octet-stream'}
    response = query_rest_api(
        '/batches', data=batch, headers=headers)
    response = submit_request('{}'.format(response['link']))
    return response


def query_rest_api(suffix='', data=None, headers=None):
    if headers is None:
        headers = {}
    url = 'http://rest-api:8080' + suffix
    return submit_request(urllib.request.Request(url, data, headers))


def submit_request(request):
    response = urllib.request.urlopen(request).read().decode('utf-8')
    return json.loads(response)


def make_batches(keys):
    imf = IntkeyMessageFactory()
    return [imf.create_batch([('set', k, 0)]) for k in keys]


class TestNamespacePermission(unittest.TestCase):
    def test_namespace_permission(self):
        """Tests that namespace permission onchain are letting block_info
        transactions be injected and preventing intkey transactions to
        be validated.
        """
        batches = make_batches('abcd')

        # Assert all block info transactions are committed
        for i, batch in enumerate(batches):
            post_batch(batch)
            time.sleep(1)
            block_info = get_block_info(i)
            self.assertEqual(block_info.block_num, i)

        # Assert block info batches are first in the block and
        # no other batch is included
        for block in get_blocks()[:-1]:
            LOGGER.debug(block['header']['block_num'])
            family_name = \
                block['batches'][0]['transactions'][0]['header']['family_name']
            self.assertEqual(family_name, 'block_info')
            self.assertEqual(len(block['batches']), 1)

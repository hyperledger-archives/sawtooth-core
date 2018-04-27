# Copyright 2018 Intel Corporation
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

import time
import unittest

from sawtooth_block_info.processor.handler \
import validate_hex, validate_timestamp
from sawtooth_block_info.protobuf.block_info_pb2 import BlockInfo
from sawtooth_block_info.common import DEFAULT_SYNC_TOLERANCE

def create_block_info(block_num,
                      signer_public_key="2" * 66,
                      header_signature="1" * 128,
                      timestamp=None,
                      previous_block_id="0" * 128):
    if timestamp is None:
        timestamp = int(time.time())

    return BlockInfo(
        block_num=block_num,
        signer_public_key=signer_public_key,
        header_signature=header_signature,
        timestamp=timestamp,
        previous_block_id=previous_block_id)

class TestHandler(unittest.TestCase):

    def test_validate_hex_previd(self):
        """ Tests previous block id is in valid hex """
        block_info = create_block_info(block_num=1)
        previd_hex = validate_hex(block_info.previous_block_id, 128)
        self.assertEqual(previd_hex, True)

    def test_validate_hex_sign_public_key(self):
        """ Tests signer public key is in valid hex """
        block_info = create_block_info(block_num=1)
        public_key_hex = validate_hex(block_info.signer_public_key, 66)
        self.assertEqual(public_key_hex, True)

    def test_validate_hex_header_sign_key(self):
        """ Tests header signature is in valid hex """
        block_info = create_block_info(block_num=1)
        header_signature_hex = validate_hex(block_info.header_signature, 128)
        self.assertEqual(header_signature_hex, True)

    def test_validate_timestamp(self):
        """ Tests the timestamp is greater than zero """
        block_info = create_block_info(block_num=1)
        now = time.time()
        if (block_info.timestamp - now) < DEFAULT_SYNC_TOLERANCE:
            validate_timestamp(block_info.timestamp, DEFAULT_SYNC_TOLERANCE)
            self.assertTrue(True)

    def test_validate_hex_ve(self):
        string_hex = validate_hex("test", 128)
        self.assertEqual(string_hex, False)


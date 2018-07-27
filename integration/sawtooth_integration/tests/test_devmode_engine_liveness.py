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

# pylint: disable=bare-except

import time
import unittest
import logging

import requests


LOGGER = logging.getLogger(__name__)

URL = 'http://rest-api-%d:8008'

# The number of nodes in the test (this needs to match the test's compose file)
NODES = 5

# Blocks must have between this many batches
BATCHES_PER_BLOCK_RANGE = (1, 100)

# At the end of the test, this many batches must be in the chain
MIN_TOTAL_BATCHES = 100

# All nodes must reach this block for the test to pass.
BLOCK_TO_REACH = 55

# Once all nodes reach the BLOCK_TO_REACH, the test will check for consensus at
# this block. These are different because PoET occassionally forks.
BLOCK_TO_CHECK_CONSENSUS = 52


class TestDevmodeEngineLive(unittest.TestCase):
    def test_liveness(self):
        """Test that a devmode network publishes blocks and stays in
        consensus."""

        # Wait until all nodes have reached the minimum block number
        nodes_reached = set()
        while len(nodes_reached) < NODES:
            for i in range(0, NODES):
                block = get_block(i)
                if block is not None:

                    # Ensure all blocks have an acceptable number of batches
                    self.assertTrue(check_block_batch_count(
                        block, BATCHES_PER_BLOCK_RANGE))
                    if int(block["header"]["block_num"]) >= BLOCK_TO_REACH:
                        nodes_reached.add(i)

                    log_block(i, block)

            time.sleep(15)

        chains = [get_chain(node) for node in range(0, NODES)]

        # Ensure all nodes are in consensus on the target block
        self.assertTrue(check_consensus(chains, BLOCK_TO_CHECK_CONSENSUS))

        # Assert an acceptable number of batches were committed
        self.assertTrue(check_min_batches(chains[0], MIN_TOTAL_BATCHES))


def get_block(node):
    try:
        result = requests.get((URL % node) + "/blocks?count=1")
        result = result.json()
        try:
            return result["data"][0]
        except:
            LOGGER.warning(result)
    except:
        LOGGER.warning("Couldn't connect to REST API %s", node)


def get_chain(node):
    try:
        result = requests.get((URL % node) + "/blocks")
        result = result.json()
        try:
            return result["data"]
        except:
            LOGGER.warning(result)
    except:
        LOGGER.warning("Couldn't connect to REST API %s", node)


def log_block(node, block):
    batches = block["header"]["batch_ids"]
    batches = [b[:6] + '..' for b in batches]
    LOGGER.warning(
        "Validator-%s has block %s: %s, batches (%s): %s",
        node,
        block["header"]["block_num"],
        block["header_signature"][:6] + '..',
        len(batches),
        batches)


def check_block_batch_count(block, batch_range):
    batch_count = len(block["header"]["batch_ids"])

    valid = batch_range[0] <= batch_count <= batch_range[1]

    if not valid:
        LOGGER.error(
            "Block (%s, %s) had %s batches in it",
            block["header"]["block_num"],
            block["header_signature"],
            batch_count)

    return valid


def check_min_batches(chain, min_batches):
    n = sum([len(block["header"]["batch_ids"]) for block in chain])
    return n >= min_batches


def check_consensus(chains, block_num):
    blocks = []
    for chain in chains:
        if chain is not None:
            block = chain[-(block_num + 1)]
            blocks.append(block)
        else:
            return False
    b0 = blocks[0]
    for b in blocks[1:]:
        if b0["header_signature"] != b["header_signature"]:
            LOGGER.error("Validators not in consensus on block %s", block_num)
            LOGGER.error("BLOCK DUMP: %s", blocks)
            return False
    return True

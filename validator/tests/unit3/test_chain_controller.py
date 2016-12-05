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

import pprint
import unittest

from sawtooth_validator.journal.journal import \
    ChainController
from sawtooth_validator.journal.consensus.test_mode.test_mode_consensus \
    import \
    BlockVerifier as TestModeVerifier

from sawtooth_validator.server.messages import BlockRequestMessage


from tests.unit3.gossip_mock import GossipMock
from tests.unit3.block_tree_manager import BlockTreeManager
from tests.unit3.syncronous_executor import SynchronousExecutor
from tests.unit3.transaction_executor_mock import TransactionExecutorMock


pp = pprint.PrettyPrinter(indent=4)


class TestChainController(unittest.TestCase):
    def setUp(self):
        self.blocks = BlockTreeManager()
        self.gossip = GossipMock()
        self.executor = SynchronousExecutor()
        self.txn_executor = TransactionExecutorMock()

        def chain_updated(head):
            pass

        self.chain_ctrl = ChainController(
            consensus=TestModeVerifier(),
            block_store=self.blocks.block_store,
            send_message=self.gossip.send_message,
            executor=self.executor,
            transaction_executor=TransactionExecutorMock(),
            on_chain_updated=chain_updated)

    def test_simple_case(self):
        # TEST Run the simple case
        block_1 = self.blocks.generate_block(self.blocks.chain_head)
        self.chain_ctrl.on_block_received(block_1)
        self.executor.process_all()
        assert (self.chain_ctrl.chain_head.id == block_1.id)

    def test_alternate_genesis(self):
        # TEST Run generate and alternate genesis block
        head = self.chain_ctrl.chain_head

        other_genesis = self.blocks.generate_block(add_to_store=True)
        for b in self.blocks.generate_chain(other_genesis, 5):
            self.chain_ctrl.on_block_received(b)
            self.executor.process_all()
        assert (self.chain_ctrl.chain_head.id == head.id)

    def test_bad_block_signature(self):
        # TEST Bad block extending current chain
        # Bad due to signature
        head = self.blocks.chain_head
        block_bad = self.blocks.generate_block(self.blocks.chain_head,
                                               invalid_signature=True)
        self.chain_ctrl.on_block_received(block_bad)
        assert (self.chain_ctrl.chain_head.id == head.id)

    def test_bad_block_consensus(self):
        # Bad due to consensus
        pass

    def test_bad_block_transaction(self):
        # Bad due to transaction
        pass

    def test_missing_block(self):
        # TEST Missing block G->missing->B
        head = self.blocks.chain_head
        new_blocks = self.blocks.generate_chain(head, 2)
        self.chain_ctrl.on_block_received(new_blocks[1])
        self.executor.process_all()
        assert(len(self.gossip.messages) == 1)
        msg = self.gossip.messages[0]
        assert (isinstance(msg, BlockRequestMessage))
        assert (msg.block_id == new_blocks[0].id)
        self.gossip.clear()
        self.chain_ctrl.on_block_received(new_blocks[0])
        self.executor.process_all()
        assert (self.chain_ctrl.chain_head.id == new_blocks[1].id)

    def test_missing_block_invalid_head(self):
        # TEST Missing block G->missing->B
        #  B is invalid but Missing is valid
        head = self.blocks.chain_head
        new_blocks_def = self.blocks.generate_chain_definition(2)
        new_blocks_def[1]["invalid_signature"] = True
        new_blocks = self.blocks.generate_chain(head, new_blocks_def)
        self.chain_ctrl.on_block_received(new_blocks[1])
        self.executor.process_all()
        assert (len(self.gossip.messages) == 1)
        msg = self.gossip.messages[0]
        assert (isinstance(msg, BlockRequestMessage))
        assert (msg.block_id == new_blocks[0].id)
        self.gossip.clear()
        self.chain_ctrl.on_block_received(new_blocks[0])
        self.executor.process_all()

        pp.pprint(new_blocks)
        pp.pprint(self.blocks.block_store)
        # TBD assert (self.chain_ctrl.chain_head.id == new_blocks[0].id)

    # TESTS TBD
    # TEST Missing block never sent G->missing->B
    # validate waiting time out....

    # TEST Run generate a fork -- current chain valid

    # TEST Run generate a fork -- fork chain valid

    # TEST variable block weights

    # TEST Run generate a fork -- fork with missing block in chain

    # TEST Run generate a fork -- bad block in middle of fork

    # TEST Run generate a fork - chain advances before fork resolves

    # TEST Run generate a fork - fork advances before fork resolves

    # TEST Run random cases thru - 2-3 forks extending at random,
    # then pick a winner

    # block arrives that extends block being validated. --
    # should be keeping a
    # fork state?

    # next multi threaded
    # next add block publisher
    # next batch lists
    # integrate with LMDB
    # early vs late binding ( class member of consensus BlockPublisher)

    # print(journal.chain_head, new_block)

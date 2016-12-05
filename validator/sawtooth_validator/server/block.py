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
import random
import string
import time
from enum import Enum

logger = logging.getLogger(__name__)


NullIdentifier = "0000000000000000"


class BlockStatus(Enum):
    Unknown = 0,
    Invalid = 1,
    Valid = 2,


def _generate_id(length=16):
    return ''.join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(length))


class BlockState(object):
    """ The state of a block stored in the block_store,
    contains additional computed state on the block that is not
    shared with other validators on the network.
    """

    def __init__(self, block):
        """Constructor for the TransactionBlock class.
        """
        self.block = block
        self.weight = 0
        self.status = BlockStatus.Unknown

    @property
    def id(self):
        return self.block.id

    @property
    def block_num(self):
        return self.block.block_num

    @property
    def previous_block_id(self):
        return self.block.previous_block_id

    @property
    def consensus(self):
        return self.block.consensus

    @property
    def signature(self):
        return self.block.signature

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return "BLKS {}:{}({}, {})".format(self.block.id, self.block.block_num,
                                           self.status, self.weight)


class Block(object):
    """A Transaction Block is a set of transactions to be applied to
    the ledger.

    Attributes:

    """

    def __init__(self, previous_block=None):
        """Constructor for the TransactionBlock class.
        """
        self.id = _generate_id()
        self.previous_block_id = previous_block.id if previous_block is not \
            None else NullIdentifier
        # TBD self.originator_id = NullIdentifier
        self.block_num = previous_block.block_num + 1 \
            if previous_block is not None else 0
        self.commit_time = time.time()
        self.consensus = None
        self.batches = []
        self.signature = None

    def __str__(self):
        return "{}:{}".format(self.id, self.block_num)

    def __repr__(self):
        return "BLK {}:{}".format(self.id, self.block_num)

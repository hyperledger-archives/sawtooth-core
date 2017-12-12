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


class MockCompleter:
    def __init__(self):
        self.blocks = {}
        self.batches = {}

    def get_block(self, block_id):
        return self.blocks.get(block_id)

    def get_batch(self, batch_id):
        return self.batches.get(batch_id)

    def add_block(self, block_id):
        self.blocks[block_id] = 1

    def add_batch(self, batch_id):
        self.batches[batch_id] = 1


class MockChainController:
    def __init__(self):
        self.blocks = {}

    def has_block(self, block_id):
        if block_id in self.blocks:
            return True
        return False

    def add_block(self, block_id):
        self.blocks[block_id] = 1


class MockPublisher:
    def __init__(self):
        self.batches = []

    def has_batch(self, batch_id):
        if batch_id in self.batches:
            return True
        return False

    def add_batch(self, batch_id):
        self.batches.append(batch_id)

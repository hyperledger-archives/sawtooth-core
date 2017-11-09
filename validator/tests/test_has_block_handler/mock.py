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

    def get_block(self, block_id):
        print(self.blocks)
        return self.blocks.get(block_id)

    def add_block(self, block_id):
        self.blocks[block_id] = 1

class MockChainController:
    def __init__(self):
        self.blocks = {}

    def has_block(self, block_id):
        print(self.blocks)
        if block_id in self.blocks:
            return True
        return False

    def add_block(self, block_id):
        self.blocks[block_id] = 1

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


class MockGossip():
    def __init__(self):
        self.broadcasted = {}
        self.sent = {}

    def broadcast(self, message, message_type, exclude):
        if message_type in self.broadcasted:
            self.broadcasted[message_type] += [message]
        else:
            self.broadcasted[message_type] = [message]

    def send(self, message_type, message_data, connection_id):
        if connection_id in self.sent:
            self.sent[connection_id] += [(message_type, message_data)]
        else:
            self.sent[connection_id] = [(message_type, message_data)]

    def clear(self):
        self.broadcasted = {}
        self.sent = {}


class MockCompleter():
    def __init__(self):
        self.store = {}

    def add_block(self, block):
        self.store[block.header_signature] = block

    def add_batch(self, batch):
        self.store[batch.header_signature] = batch
        for txn in batch.transactions:
            self.store[txn.header_signature] = batch

    def get_chain_head(self):
        pass

    def get_block(self, block_id):
        return self.store.get(block_id)

    def get_batch(self, batch_id):
        return self.store.get(batch_id)

    def get_batch_by_transaction(self, transaction_id):
        return self.store.get(transaction_id)

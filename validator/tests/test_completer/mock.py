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
        self.requested_blocks = []
        self.requested_batches = []
        self.requested_batches_by_txn_id = []

    def broadcast_block_request(self, block_id):
        self.requested_blocks.append(block_id)

    def broadcast_batch_by_batch_id_request(self, batch_id):
        self.requested_batches.append(batch_id)

    def broadcast_batch_by_transaction_id_request(self, transaction_ids):
        for txn_id in transaction_ids:
            self.requested_batches_by_txn_id.append(txn_id)

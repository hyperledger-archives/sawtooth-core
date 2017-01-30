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


from sawtooth_validator.scheduler.base import Scheduler
from sawtooth_validator.scheduler.base import BatchExecutionResult


class SchedulerMock(Scheduler):
    def add_batch(self, batch, state_hash=None):
        pass

    def get_batch_execution_result(self, batch_signature):
        return BatchExecutionResult(is_valid=True, state_hash="0000000000")

    def set_transaction_execution_result(
            self, txn_signature, is_valid, context_id):
        raise NotImplementedError()

    def next_transaction(self):
        raise NotImplementedError()

    def finalize(self):
        pass

    def complete(self, block):
        return True

    def __iter__(self):
        raise NotImplementedError()

    def get_transaction(self, index):
        raise NotImplementedError()

    def count(self):
        raise NotImplementedError()

class TransactionExecutorMock(object):
    def __init__(self):
        self.messages = []

    def create_scheduler(self, squash_handler, first_state_root):
        return SchedulerMock()

    def execute(self, scheduler, state_hash=None):
        pass

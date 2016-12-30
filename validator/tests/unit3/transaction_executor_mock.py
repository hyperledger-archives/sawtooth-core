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


class BatchStatus(object):
    def __init__(self, status, state_hash):
        self.valid = status
        self.state_hash = state_hash


class SchedulerMock(object):
    def add_batch(self, batch, state_hash=None):
        pass

    def finalize(self):
        pass

    def complete(self):
        return True

    def batch_status(self, batch_id):
        return BatchStatus(True, "0000000000")


class TransactionExecutorMock(object):
    def __init__(self):
        self.messages = []

    def create_scheduler(self, squash_handler, first_state_root):
        return SchedulerMock()

    def execute(self, scheduler, state_hash=None):
        pass

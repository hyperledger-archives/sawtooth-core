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

# import bitcoin

from sawtooth_validator.server.plan import SerialExecutionPlanGenerator


class FauxJournal(object):
    def __init__(self, executor):
        self._executor = executor

    def get_on_batch_received_handler(self):
        def _handler(batch):
            return self.on_batch_received(batch)
        return _handler

    def on_batch_received(self, batch):
        generator = SerialExecutionPlanGenerator()
        plan = generator.generate_plan(batch.transactions)

        results = self._executor.execute(plan, batch.transactions)
        print "processed {}".format(len(results))

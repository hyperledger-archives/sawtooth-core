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

from sawtooth_validator.scheduler.serial import SerialScheduler


class FauxJournal(object):
    def __init__(self, executor):
        self._executor = executor

        # In a full implementation, there would be one scheduler
        # for each chain the Journal wanted to process but only
        # a single executor.  We create a single scheduler for now
        # and hook it to the executor.
        self._scheduler = SerialScheduler()
        self._executor.execute(self._scheduler)

    def get_on_batch_received_handler(self):
        def _handler(batch):
            return self.on_batch_received(batch)
        return _handler

    def on_batch_received(self, batch):
        self._scheduler.add_batch(batch)

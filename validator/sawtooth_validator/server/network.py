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

import sawtooth_validator.protobuf.batch_pb2 as batch_pb2


class FauxNetwork(object):
    def __init__(self, dispatcher):
        self._dispatcher = dispatcher

    def _verify_batch(self, batch):
        pass

    def load(self, data):
        batch_list = batch_pb2.BatchList()
        batch_list.ParseFromString(data)

        for batch in batch_list.batches:
            self._verify_batch(batch)
            self._dispatcher.on_batch_received(batch)

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


# expect all of these to be replace with protobuffers.


class BlockRequestMessage(object):
    """
    Place holder for requests for missing block
    """

    def __init__(self, block_id):
        self.block_id = block_id


class BlockMessage(object):
    def __init__(self, block):
        self.block = block


class BatchMessage(object):
    def __init__(self, batch):
        self.block = batch

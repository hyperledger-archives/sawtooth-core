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

NAMESPACE = '00b10c'
BLOCK_INFO_NAMESPACE = NAMESPACE + '00'
CONFIG_ADDRESS = NAMESPACE + '01' + '0' * 62


def create_block_address(block_num):
    return BLOCK_INFO_NAMESPACE + hex(block_num)[2:].zfill(62)

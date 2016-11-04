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

from consensus.poet0.poets_client import poets_enclave

__all__ = ['poets_enclave', 'wait_timer', 'wait_certificate']

NULL_IDENTIFIER = poets_enclave.NULL_IDENTIFIER
IDENTIFIER_LENGTH = poets_enclave.IDENTIFIER_LENGTH
MINIMUM_WAIT_TIME = poets_enclave.MINIMUM_WAIT_TIME

initialize = poets_enclave.initialize
create_wait_timer = poets_enclave.create_wait_timer
deserialize_wait_timer = poets_enclave.deserialize_wait_timer
create_wait_certificate = poets_enclave.create_wait_certificate
deserialize_wait_certificate = poets_enclave.deserialize_wait_certificate
verify_wait_certificate = poets_enclave.verify_wait_certificate

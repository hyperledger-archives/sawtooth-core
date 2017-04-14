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


# ValidatorConnectionError is used internal to the sdk, and
# any other use can cause undesirable or unexpected behavior.
class ValidatorConnectionError(Exception):
    def __init__(self):
        super().__init__("the connection to the validator was lost")


class WorkloadConfigurationError(Exception):
    def __init__(self):
        super().__init__("A workload object is not set.")

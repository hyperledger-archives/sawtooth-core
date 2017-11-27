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

'''The processor module defines:

1. A TransactionHandler interface to be
used to create new transaction families.

2. A high-level, general purpose TransactionProcessor to which any
number of handlers can be added.

3. A Context class used to abstract getting and setting addresses in
global validator state.
'''

__all__ = [
    'core',
    'context',
    'exceptions'
]

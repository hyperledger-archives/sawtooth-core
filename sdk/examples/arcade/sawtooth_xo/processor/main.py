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

import hashlib
import sys

from sawtooth_sdk.processor.core import TransactionProcessor

from arcade.sawtooth_xo.processor.handler import XoTransactionHandler


def main(args=sys.argv[1:]):
    # The prefix should eventually be looked up from the
    # validator's namespace registry.
    xo_prefix = hashlib.sha512('xo'.encode("utf-8")).hexdigest()[0:6]

    url = args[0] if len(args) > 0 else "0.0.0.0"
    processor = TransactionProcessor(url=url + ":40000")

    handler = XoTransactionHandler(namespace_prefix=xo_prefix)
    processor.add_handler(handler)

    processor.start()

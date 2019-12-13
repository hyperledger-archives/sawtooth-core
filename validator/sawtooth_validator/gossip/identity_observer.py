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
import logging

from sawtooth_validator.journal.chain import ChainObserver
from sawtooth_validator.journal.event_extractors import \
    BlockEventExtractor
from sawtooth_validator.journal.event_extractors import \
    ReceiptEventExtractor
from sawtooth_validator.server.events.subscription import EventSubscription

LOGGER = logging.getLogger(__name__)


class IdentityObserver(ChainObserver):
    """
    The Identity Observer is used to update the local permission verifier's
    caches of identity data when an Identity transaction is committed.
    """

    def __init__(self, to_update, forked):
        # function to notify the permission verifier to update the caches
        self.to_update = to_update
        # function to notify the permission verifier there has been a
        # fork and that the entries in the cache should be invalidated
        self.forked = forked
        self.last_block_id = None

    def chain_update(self, block, receipts):
        """
        Handles both "sawtooth/block-commit" Events and "identity/update"
        Events. For "sawtooth/block-commit", the last_block_num is updated or a
        fork is detected. For "identity/update", the corresponding cache entry
        will be updated.
        """

        block_events = BlockEventExtractor(block).extract([
            EventSubscription(event_type="sawtooth/block-commit")])
        receipt_events = ReceiptEventExtractor(receipts).extract([
            EventSubscription(event_type="identity/update")])

        for event in block_events:
            forked = self._handle_block_commit(event)
            if forked:
                return

        for event in receipt_events:
            if event.event_type == "identity/update":
                self._handle_txn_commit(event)

    def _handle_txn_commit(self, event):
        updated = event.attributes[0].value
        self.to_update(updated)

    def _handle_block_commit(self, event):
        # if the new block's previous block id does not match the previous
        # block that we have seen, there has been a fork.
        previous_block_id = event.attributes[3].value
        block_id = event.attributes[0].value
        if previous_block_id == self.last_block_id:
            self.last_block_id = block_id
            return False

        self.forked()
        self.last_block_id = block_id
        return True

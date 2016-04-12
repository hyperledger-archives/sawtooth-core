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

import logging

from txnserver import validator
from journal.consensus.poet import poet_journal, wait_certificate
from ledger.transaction import endpoint_registry

logger = logging.getLogger(__name__)


class LotteryValidator(validator.Validator):
    EndpointDomain = '/LotteryValidator'

    def __init__(self, config, windows_service=False):
        super(LotteryValidator, self).__init__(config, windows_service)

    def initialize_ledger_specific_configuration(self):
        """
        Initialize any ledger type specific configuration options, expected to
        be overridden
        """

        # Handle all of the configuration variables
        if 'TargetWaitTime' in self.Config:
            wait_certificate.WaitTimer.target_wait_time = \
                float(self.Config['TargetWaitTime'])

        if 'InitialWaitTime' in self.Config:
            wait_certificate.WaitTimer.initial_wait_time = \
                float(self.Config['InitialWaitTime'])

        if 'CertificateSampleLength' in self.Config:
            wait_certificate.WaitTimer.certificate_sample_length = int(
                self.Config['CertificateSampleLength'])
            wait_certificate.WaitTimer.fixed_duration_blocks = \
                int(self.Config['CertificateSampleLength'])

        if 'FixedDurationBlocks' in self.Config:
            wait_certificate.WaitTimer.fixed_duration_blocks = \
                int(self.Config['FixedDurationBlocks'])

        if 'MinTransactionsPerBlock' in self.Config:
            poet_journal.PoetJournal.MinimumTransactionsPerBlock = int(
                self.Config['MinTransactionsPerBlock'])

        if 'MaxTransactionsPerBlock' in self.Config:
            poet_journal.PoetJournal.MaximumTransactionsPerBlock = int(
                self.Config['MaxTransactionsPerBlock'])

    def initialize_ledger_from_node(self, node):
        """
        Initialize the ledger object for the local node, expected to be
        overridden
        """
        self.Ledger = poet_journal.PoetJournal(node, **self.Config)

    def register_endpoint(self, node, domain='/'):

        txn = endpoint_registry.EndpointRegistryTransaction.create_from_node(
            node, domain)
        txn.sign_from_node(node)

        msg = endpoint_registry.EndpointRegistryTransactionMessage()
        msg.Transaction = txn
        msg.SenderID = str(node.Identifier)
        msg.sign_from_node(node)

        logger.info('register endpoint %s with name %s', node.Identifier[:8],
                    node.Name)
        self.Ledger.handle_message(msg)

    def unregister_endpoint(self, node, domain='/'):
        update = endpoint_registry.Update.create_from_node(node, domain)
        update.Verb = 'unr'

        txn = endpoint_registry.EndpointRegistryTransaction()
        txn.Updates.append(update)
        txn.sign_from_node(node)

        # Since unregister is often called on shutdown, we really need to make
        # this a system message for the purpose of sending it out from our own
        # queue
        msg = endpoint_registry.EndpointRegistryTransactionMessage()
        msg.IsSystemMessage = True
        msg.Transaction = txn
        msg.SenderID = str(node.Identifier)
        msg.sign_from_node(node)

        logger.info('unregister endpoint %s with name %s', node.Identifier[:8],
                    node.Name)
        self.Ledger.handle_message(msg)

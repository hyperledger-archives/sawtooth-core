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
import traceback
import sys

from collections import namedtuple, deque
from twisted.internet import task
from twisted.internet import reactor

from sawtooth.client import TransactionStatus, ClientState
from sawtooth.exceptions import MessageException


PendingTransaction = namedtuple('PendingTransaction', ['id', 'validator'])

LOGGER = logging.getLogger(__name__)


class EndpointRegistryState(ClientState):
    def __init__(self, base_url):
        super(EndpointRegistryState, self).__init__(
            base_url, 'EndpointRegistryTransaction')

    @property
    def validators(self):
        self.fetch()
        return ['http://{0}:{1}'.format(
            transaction['Host'], transaction['HttpPort']) for
            transaction in self.state.values()]


class SawtoothWorkloadSimulator(object):
    def __init__(self, opts):
        self._loop = None
        self._pending_transactions = deque()
        self._base_validator = opts.url
        self._validators = []

        # Dynamically load the workload class' module and create a workload
        # generator
        components = opts.workload.split('.')
        module = __import__('.'.join(components[:-1]),
                            fromlist=[components[-1]])
        workload = getattr(module, components[-1])
        self._workload = workload(delegate=self)

        # Prime the workload generator with the validators we currently know
        # about
        self._discover_validators()

        # Give the workload generator one last chance to set up anything
        # before we start the simulator loop
        self._workload.on_will_start()

        # Set up the looping call for stepping through the simulator.  The
        # provided rate is number of transactions per minute, so we calculate
        # the number of seconds between transactions and that becomes the
        # loop rate.
        LOGGER.info('Simulator will generate %s transaction(s)/minute',
                    opts.rate)
        loop = task.LoopingCall(self._step)
        deferred = loop.start(60.0 / float(opts.rate), now=False)
        deferred.addCallback(self._loop_cleanup)

        # Set up the looping call for discovering validators.  The provided
        # rate is in minutes between checks, so convert to seconds.
        LOGGER.info('Simulator will discover validators every %s minute(s)',
                    opts.discover)
        loop = task.LoopingCall(self._discover_validators)
        loop.start(opts.discover * 60, now=False)

    def run(self):
        # pylint: disable=no-self-use
        reactor.run()

    def _step(self):
        # If there are pending transactions, then pull off the first one
        # and check its status.
        if len(self._pending_transactions) > 0:
            transaction = self._pending_transactions.popleft()

            # pylint: disable=bare-except
            try:
                status = \
                    transaction.validator.headrequest(
                        '/transaction/{0}'.format(transaction.id))
                if status == TransactionStatus.committed:
                    self._workload.on_transaction_committed(transaction.id)
                else:
                    # If the workload generator wants the pending
                    # transaction to be checked again, we are going to make
                    # sure that the transaction is checked on the next
                    # "step" as this is the oldest transaction.
                    if self._workload.on_transaction_not_yet_committed(
                            transaction.id):
                        self._pending_transactions.appendleft(transaction)

            except MessageException as e:
                # A MessageException means that we cannot talk to the
                # validator.  In that case, we are going to remove it
                # from the list of validators and immediately let the
                # workload generator know that it has gone away.
                LOGGER.warn('Validator %s not responding: %s',
                            transaction.validator.base_url,
                            e)
                if transaction.validator.base_url in self._validators:
                    self._workload.on_validator_removed(
                        transaction.validator.base_url)
                    self._validators.remove(transaction.validator.base_url)
            except:
                # Something has gone really wrong.  Print out a traceback
                # and then stop the reactor, which stops the simulator.
                # We do it this way because twisted seems to want to catch
                # the exception and print the traceback, but it doesn't appear
                # to want to stop the reactor (maybe because we have another
                # loop running in the reactor).
                traceback.print_exc(file=sys.stderr)
                reactor.stop()

        # Otherwise, let workload generator know that there are no
        # uncommitted transactions
        else:
            self._workload.on_all_transactions_committed()

    def _discover_validators(self):
        # Find out which validators are in the network currently.  Because
        # validators can crash and other validators don't reflect that in
        # their endpoint registry, we are going to treat this like a depth
        # first search.  We'll start with the list of candidate validators
        # we know about and then as we discover new ones, we add them to
        # the list of candidates.  If we don't have any validators, we will
        # rely on the base validator to prime the list for us.
        validators = []
        discovered = \
            list(self._validators) \
            if len(self._validators) > 0 else [self._base_validator]
        candidates = list(discovered)
        while len(candidates) > 0:
            # Grab a candidate to query
            candidate = candidates.pop()
            try:
                # Get the validators that this candidate knows about.  For the
                # validators not in the discovered list:
                # - add the ones not already in the candidate list to the
                #   candidates
                # - add all newly-discovered validators to the discovered
                new_validators = \
                    [v for v in EndpointRegistryState(candidate).validators
                     if v not in discovered]
                candidates.extend(
                    [v for v in new_validators if v not in candidates])
                discovered.extend(new_validators)

                # Since this candidate responded, add it to the list of
                # validators
                validators.append(candidate)
            except MessageException as e:
                LOGGER.warn('Failed to get endpoint registry from validator '
                            '%s: %s',
                            candidate,
                            e)

        # Determine which validators have been discovered and removed since
        # the last time
        discovered = [v for v in validators if v not in self._validators]
        removed = [v for v in self._validators if v not in validators]

        # First let the workload generator know about additions then removals
        for validator in discovered:
            LOGGER.info('Discovered a new validator: %s', validator)
            self._workload.on_validator_discovered(validator)
        for validator in removed:
            LOGGER.info('Remove validator: %s', validator)
            self._workload.on_validator_removed(validator)

        # Save off the list of validators
        self._validators = validators

    def on_new_transaction(self, transaction_id, client):
        """
        Called by the workload generator to let the simulator know that a new
        transaction should be tracked.

        Args:
            transaction_id: The ID for the new transaction
            client: The validator to which the transaction has been submitted.
              This object should support the public methods in SawtoothClient.

        Returns:
            Nothing
        """
        if transaction_id is not None:
            self._pending_transactions.append(
                PendingTransaction(id=transaction_id, validator=client))

    def _loop_cleanup(self, result):
        self._workload.on_will_stop()
        reactor.stop()

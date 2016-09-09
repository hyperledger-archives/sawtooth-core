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
import threading
import time

from collections import namedtuple, deque
from twisted.internet import task
from twisted.internet import reactor

from sawtooth.client import TransactionStatus
from sawtooth.exceptions import MessageException
from sawtooth.endpoint_client import EndpointClient


PendingTransaction = namedtuple('PendingTransaction', ['id', 'client'])

LOGGER = logging.getLogger(__name__)


class SawtoothWorkloadSimulator(object):
    def __init__(self, config):
        self._loop = None
        self._base_validator = config.get('Simulator', 'url')
        self._is_throttling = False
        self._lock = threading.Lock()

        # For now, let's try 20 maximum outstanding work requests.  Through
        # experimentation it appears that the twisted reactor main thread pool
        # has 10 threads.  We are going to allow twice as many outstanding
        # work requests before we start to throttle them.
        self._maximum_outstanding_requests = 20

        # These attributes need to be protected by self._lock.  Ensure
        # that any threaded access grabs the lock before reading/writing.
        self._pending_transactions = deque()
        self._validators = []
        self._is_performing_discovery = False
        self._number_of_outstanding_requests = 0
        self._submitted_transactions_sample = 0
        self._committed_transactions_sample = 0

        # Used to calculate rough approximations of transactions/minute.
        # We'll set it to a real time later.
        self._time_since_last_check = 0
        self._submitted_transaction_samples = deque()
        self._committed_transaction_samples = deque()

        # Dynamically load the workload class' module and create a workload
        # generator
        components = config.get('Simulator', 'workload').split('.')
        module = __import__('.'.join(components[:-1]),
                            fromlist=[components[-1]])
        workload = getattr(module, components[-1])
        self._workload = workload(delegate=self, config=config)

        # Prime the workload generator with the validators we currently know
        # about
        self._discover_validators()

        # Give the workload generator one last chance to set up anything
        # before we start the simulator loop
        self._workload.on_will_start()

        # Set up the looping call for stepping through the simulator.  The
        # provided rate is the number of transactions per minute, so we
        # calculate the number of seconds between transactions and that
        # becomes the loop rate.
        rate = config.getint('Simulator', 'rate')
        LOGGER.info('Simulator will generate %d transaction(s)/minute', rate)
        loop = task.LoopingCall(self._simulator_loop)
        deferred = loop.start(60.0 / rate, now=False)
        deferred.addCallback(self._loop_cleanup)

        self._update_frequency = config.getint('Simulator', 'update_frequency')

        # Set up the looping call for discovering validators.  The provided
        # rate is in minutes between checks, so convert to seconds.
        discover = config.getint('Simulator', 'discover')
        LOGGER.info('Simulator will discover validators every %d minute(s)',
                    discover)
        loop = task.LoopingCall(self._discover_validators_loop)
        loop.start(discover * 60, now=False)

    def run(self):
        # pylint: disable=no-self-use
        self._time_since_last_check = time.time()
        reactor.run()

    def _simulator_loop(self):
        with self._lock:
            # Check the time.  If at least a update_frequency seconds
            # has passed since we have last report transactions/minute,
            # then let's do so
            now = time.time()
            delta = now - self._time_since_last_check
            if delta >= self._update_frequency:
                # Take the samples and normalize to a minute.
                sample = 60 * \
                    (self._submitted_transactions_sample / delta)
                self._submitted_transaction_samples.append(sample)
                LOGGER.warn(
                    'Transaction submission rate for last sample period is '
                    '%.2f tpm',
                    sample)

                sample = 60 * \
                    (self._committed_transactions_sample / delta)
                self._committed_transaction_samples.append(sample)
                LOGGER.warn(
                    'Transaction commit rate for last sample period is '
                    '%.2f tpm',
                    sample)

                # We are going to only use at most the last 10 samples to
                # calculate the moving average
                if len(self._submitted_transaction_samples) == 11:
                    self._submitted_transaction_samples.popleft()
                    self._committed_transaction_samples.popleft()

                LOGGER.warn(
                    'Transaction submission rate for last %d sample(s) '
                    'is %.2f tpm',
                    len(self._submitted_transaction_samples),
                    sum(self._submitted_transaction_samples) /
                    len(self._submitted_transaction_samples))
                LOGGER.warn(
                    'Transaction commit rate for last %d sample(s) '
                    'is %.2f tpm',
                    len(self._committed_transaction_samples),
                    sum(self._committed_transaction_samples) /
                    len(self._committed_transaction_samples))

                self._submitted_transactions_sample = 0
                self._committed_transactions_sample = 0
                self._time_since_last_check = now

            # Only push work off to a worker thread if we have not hit the
            # maximum number of outstanding requests.  If we have hit the
            # maximum number then there really is no use issuing another
            # transaction as the validators are not keeping up right now.
            # Throttle back a little bit and let them catch their breath.
            if self._number_of_outstanding_requests \
                    < self._maximum_outstanding_requests:
                self._is_throttling = False
                self._number_of_outstanding_requests += 1

                # If there are pending transactions, then pull off the first
                # one.
                transaction = \
                    self._pending_transactions.popleft() \
                    if len(self._pending_transactions) > 0 else None

                # Let a worker thread work handle the actual work as we don't
                # want to block the main reactor thread.
                reactor.callInThread(self._check_on_transaction, transaction)
            else:
                # Only print a message when we first detect we are throttling.
                # There's no use continuing to spew the messages to the log for
                # every time we detect it.
                if not self._is_throttling:
                    LOGGER.info(
                        'Simulator is throttling work requests as the number '
                        'of outstanding work requests has reached its limit '
                        'of %d',
                        self._maximum_outstanding_requests)
                    self._is_throttling = True

    def _discover_validators_loop(self):
        # Discovering validators may take a while, so push it off into
        # another thread so we don't block the reactor main thread and thus
        # our simulator.
        #
        # Because discovery may be time consuming, we are not going to
        # allow multiple discoveries to occur at the same time as we would
        # prefer that our worker threads be issuing transactions.
        with self._lock:
            if not self._is_performing_discovery:
                self._is_performing_discovery = True
                reactor.callInThread(self._discover_validators)

    def _check_on_transaction(self, transaction):
        # If the transaction is not None, then we will check it status and
        # perform the appropriate callback into the workload generator
        if transaction is not None:
            # pylint: disable=bare-except
            try:
                status = \
                    transaction.client.get_transaction_status(
                        transaction.id)
                if status == TransactionStatus.committed:
                    with self._lock:
                        self._committed_transactions_sample += 1

                    self._workload.on_transaction_committed(transaction.id)
                elif status == TransactionStatus.server_busy:
                    # If the server is busy, we are going to take a short
                    # breather from issuing transactions and place this
                    # at the end of the pending transactions to give the
                    # validator time to catch up.
                    with self._lock:
                        LOGGER.warn(
                            'Validator %s is responding as busy',
                            transaction.client.base_url)
                        self._pending_transactions.append(transaction)
                else:
                    # If the workload generator wants the pending
                    # transaction to be checked again, we are going to make
                    # sure that the transaction is checked on the next
                    # "step" as this is the oldest transaction.
                    if self._workload.on_transaction_not_yet_committed(
                            transaction.id):
                        with self._lock:
                            self._pending_transactions.appendleft(transaction)

            except MessageException as e:
                # A MessageException means that we cannot talk to the
                # validator.  In that case, we are going to remove it
                # from the list of validators and immediately let the
                # workload generator know that it has gone away.
                LOGGER.warn('Validator %s not responding: %s',
                            transaction.client.base_url,
                            e)
                if transaction.client.base_url in self._validators:
                    self._remove_unresponsive_validator(
                        transaction.client.base_url)
            except:
                # Something has gone really wrong.  Print out a traceback
                # and then stop the reactor, which stops the simulator.
                # We do it this way because twisted seems to want to catch
                # the exception and print the traceback, but it doesn't appear
                # to want to stop the reactor (maybe because we have another
                # loop running in the reactor).
                traceback.print_exc(file=sys.stderr)
                reactor.stop()

        # If the transaction ID is None, then it means there were no
        # transactions to check during the reactor loop callback that fired
        # off this method.
        else:
            self._workload.on_all_transactions_committed()

        # Now that we are done, we can decrement the number of outstanding
        # work requests.
        with self._lock:
            self._number_of_outstanding_requests -= 1

    def _discover_validators(self):
        # Find out which validators are in the network currently.  Because
        # validators can crash and other validators don't reflect that in
        # their endpoint registry, we are going to treat this like a depth
        # first search.  We'll start with the list of candidate validators
        # we know about and then as we discover new ones, we add them to
        # the list of candidates.  If we don't have any validators, we will
        # rely on the base validator to prime the list for us.
        with self._lock:
            discovered = \
                list(self._validators) \
                if len(self._validators) > 0 else [self._base_validator]

        validators = []
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
                    [v for v
                     in EndpointClient(candidate).get_validator_url_list()
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
        LOGGER.info('Discovered %d new validators', len(discovered))
        for validator in discovered:
            LOGGER.info('Discovered a new validator: %s', validator)
            self._workload.on_validator_discovered(validator)
        LOGGER.info('Removed %d non-responsive validators', len(removed))
        for validator in removed:
            self._remove_unresponsive_validator(validator)

        # Save off the list of validators and reset the discovery flag
        LOGGER.info(
            'Running simulated workload on %d validators',
            len(validators))
        with self._lock:
            self._validators = validators
            self._is_performing_discovery = False

    def _remove_unresponsive_validator(self, validator):
        # Iterate through all pending transactions and purge the ones that
        # were submitted to the client representing this validator as it is a
        # waste to check on them.  Let the workload generator know that the
        # validator has been removed and then remove it from the list of
        # known validators.
        #
        # If the validator happens to come back, we will pick it up again
        # later when discovering validators.
        LOGGER.info('Remove validator: %s', validator)
        with self._lock:
            self._pending_transactions = \
                deque(
                    [t for t in self._pending_transactions
                     if t.client.base_url != validator])
            if validator in self._validators:
                self._validators.remove(validator)
        self._workload.on_validator_removed(validator)

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
            with self._lock:
                self._submitted_transactions_sample += 1
                self._pending_transactions.append(
                    PendingTransaction(id=transaction_id, client=client))

    def _loop_cleanup(self, result):
        self._workload.on_will_stop()
        reactor.stop()

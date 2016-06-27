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

from collections import namedtuple, deque

from twisted.internet import task
from twisted.internet import reactor

from sawtooth.client import TransactionStatus, ClientState


PendingTransaction = namedtuple('PendingTransaction', ['id', 'validator'])


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

        # Dynamically load the workload class' module and create a workload
        # generator
        components = opts.workload.split('.')
        module = __import__('.'.join(components[:-1]),
                            fromlist=[components[-1]])
        workload = getattr(module, components[-1])
        self._workload = workload(delegate=self)

        # Prime the workload generator with the validators we currently know
        # about
        self._validators = EndpointRegistryState(opts.url).validators
        for url in self._validators:
            self._workload.on_validator_discovered(url)

        # Give the workload generator one last chance to set up anything
        # before we start the simulator loop
        self._workload.on_will_start()

        # Set up the looping call for stepping through the simulator.  The
        # provided rate is number of transactions per minute, so we calculate
        # the number of seconds between transactions and that becomes the
        # loop rate.
        self._loop = task.LoopingCall(self._step)
        deferred_loop = self._loop.start(60.0 / float(opts.rate))
        deferred_loop.addCallbacks(self._loop_done, self._loop_failed)

    def run(self):
        # pylint: disable=no-self-use
        reactor.run()

    def _step(self):
        # If there are pending transactions, then pull off the first one
        # and check its status.
        if len(self._pending_transactions) > 0:
            transaction = self._pending_transactions.popleft()

            status = \
                transaction.validator.headrequest(
                    '/transaction/{0}'.format(transaction.id))
            if status == TransactionStatus.committed:
                self._workload.on_transaction_committed(transaction.id)
            else:
                # If the workload generator wants the pending transaction to be
                # checked again, we are going to make sure that the
                # transaction is checked on the next "step" as this is
                # the oldest transaction.
                if self._workload.on_transaction_not_yet_committed(
                        transaction.id):
                    self._pending_transactions.appendleft(transaction)
        # Otherwise, let workload generator know that there are no uncommitted
        # transactions
        else:
            self._workload.on_all_transactions_committed()

    def on_new_transaction(self, transaction_id, client):
        self._pending_transactions.append(
            PendingTransaction(id=transaction_id, validator=client))

    def _loop_done(self, result):
        self._workload.on_will_stop()
        reactor.stop()

    def _loop_failed(self, failure):
        self._workload.on_will_stop()
        reactor.stop()

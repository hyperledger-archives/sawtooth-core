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

import abc


class Workload(metaclass=abc.ABCMeta):
    """
       This is meant to be an abstract base class for all workloads.
       As such, it doesn't do anything useful besides
       define the interface that the workload generator expects and
       hold onto one property for derived classes.
    """

    @abc.abstractmethod
    def __init__(self, delegate, args):
        """
        Initializes the base class.

        Args:
            delegate: The object that supports delegate methods
            args: Args object that has command line arguments

        The workload uses the delegate object to alert the
        simulator of certain events.

        on_new_transaction(batch_id, stream) is called when a
        workload generator creates a new transaction.

        batch_id - the batch ID for the new batch
        stsream - An instance of the Stream class connected to a validator.
        This stream is the one to which the batch was submitted.
        """
        self._delegate = delegate

    @property
    def delegate(self):
        return self._delegate

    @abc.abstractmethod
    def on_will_start(self):
        """
        Called by the workload generator to let the workload do any final
        setup before the workload generator begins.

        Returns:
            Nothing
        """

    @abc.abstractmethod
    def on_will_stop(self):
        """
        Called by the workload generator to let the workload do any
        final cleanup before the simulator tears down.

        Returns:
            Nothing
        """

    @abc.abstractmethod
    def on_validator_discovered(self, url):
        """
        Called by the workload generator to let the workload  know that it has
        discovered a new validator in the network.

        Args:
            url: The URL for the validator

        Returns:
            Nothing
        """

    @abc.abstractmethod
    def on_validator_removed(self, url):
        """
        Called by the workload generator to let the workload know that it has
        detected that a validator has left the network.

        Args:
            url: The URL for the validator

        Returns:
            Nothing
        """

    @abc.abstractmethod
    def on_all_batches_committed(self):
        """
        In the normal course of running the workload generator loop, this is
        called by the generator to let the workload know that all pending
        transactions have been completed.  This is a hint to create a new
        batch.

        Returns:
            Nothing
        """

    @abc.abstractmethod
    def on_batch_committed(self, batch_id):
        """
        In the normal course of running the workload generator, this is called
        by the generator to let the workload know that a previously-
        pending batch has been committed by the validator to which it
        was submitted.

        Args:
            batch_id: The batch that has been committed.

        Returns:
            Nothing
        """

    @abc.abstractmethod
    def on_batch_not_yet_committed(self):
        """
        In the normal course of running the workload generator, this is called
        by the generator to let the workload know that a previously-
        pending batch's status was checked and it is not committed.


        Returns:
            Nothing

        """

# Copyright 2016-2017 Intel Corporation
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

from ast import literal_eval
from itertools import filterfalse
from threading import Condition
import logging
from collections import deque
from collections import namedtuple

from sawtooth_validator.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_validator.execution.scheduler import BatchExecutionResult
from sawtooth_validator.execution.scheduler import TxnExecutionResult
from sawtooth_validator.execution.scheduler import TxnInformation
from sawtooth_validator.execution.scheduler import Scheduler
from sawtooth_validator.execution.scheduler import SchedulerIterator
from sawtooth_validator.execution.scheduler_exceptions import SchedulerError

LOGGER = logging.getLogger(__name__)


_AnnotatedBatch = namedtuple('ScheduledBatch',
                             ['batch', 'required', 'preserve'])


class PredecessorTreeNode:
    def __init__(self, children=None, readers=None, writer=None):
        self.children = children if children is not None else {}
        self.readers = readers if readers is not None else []
        self.writer = writer

    def __repr__(self):
        retval = {}

        if self.readers:
            retval['readers'] = self.readers
        if self.writer is not None:
            retval['writer'] = self.writer
        if self.children:
            retval['children'] = \
                {k: literal_eval(repr(v)) for k, v in self.children.items()}

        return repr(retval)


class PredecessorTree:
    def __init__(self, token_size=2):
        self._token_size = token_size
        self._root = PredecessorTreeNode()

    def __repr__(self):
        return repr(self._root)

    def _tokenize_address(self, address):
        return [
            address[i:i + self._token_size]
            for i in range(0, len(address), self._token_size)
        ]

    def _get(self, address, create=False):
        tokens = self._tokenize_address(address)

        node = self._root
        for token in tokens:
            if token in node.children:
                node = node.children[token]
            else:
                if not create:
                    return None
                child = PredecessorTreeNode()
                node.children[token] = child
                node = child

        return node

    def get(self, address):
        return self._get(address)

    def add_reader(self, address, reader):
        node = self._get(address, create=True)
        node.readers.append(reader)

    def set_writer(self, address, writer):
        node = self._get(address, create=True)
        node.readers = []
        node.writer = writer
        node.children = {}

    def find_write_predecessors(self, address):
        """Returns all predecessor transaction ids for a write of the provided
        address.

        Arguments:
            address (str): the radix address

        Returns: a set of transaction ids
        """
        # A write operation must be preceded by:
        #   - The "enclosing writer", which is the writer at the address or
        #     the nearest writer higher (closer to the root) in the tree.
        #   - The "enclosing readers", which are the readers at the address
        #     or higher in the tree.
        #   - The "children writers", which include all writers which are
        #     lower in the tree than the address.
        #   - The "children readers", which include all readers which are
        #     lower in the tree than the address.
        #
        # The enclosing writer must be added as it may have modified a node
        # which must not happen after the current write.
        #
        # Writers which are higher in the tree than the enclosing writer may
        # have modified a node at or under the given address.  However, we do
        # not need to include them here as they will have been considered a
        # predecessor to the enclosing writer.
        #
        # Enclosing readers must be included.  Technically, we only need to add
        # enclosing readers which occurred after the enclosing writer, since
        # the readers preceding the writer will have been considered a
        # predecessor of the enclosing writer.  However, with the current
        # data structure we can not determine the difference between readers
        # so we specify them all; this is mostly harmless as it will not change
        # the eventual sort order generated by the scheduler.
        #
        # Children readers must be added, since their reads must happen prior
        # to the write.

        tokens = self._tokenize_address(address)

        predecessors = set()

        # First, walk down from the root to the address, collecting all readers
        # and updating the enclosing_writer if needed.

        node = self._root
        enclosing_writer = node.writer  # possibly None

        # the readers at the root node will always be added
        predecessors.update(set(node.readers))

        for token in tokens:
            # If the address isn't on the tree, then there aren't any
            # predecessors below the node to worry about (because
            # there isn't anything at all), so return the predecessors
            # that have already been collected.
            if token not in node.children:
                if enclosing_writer is not None:
                    predecessors.add(enclosing_writer)
                return predecessors

            node = node.children[token]

            # add enclosing readers directly to predecessors
            predecessors.update(set(node.readers))

            if node.writer is not None:
                enclosing_writer = node.writer

        if enclosing_writer is not None:
            predecessors.add(enclosing_writer)

        # Next, descend down the tree starting at the address node and find
        # all children writers and readers.  Uses breadth first search.

        to_process = deque()
        to_process.extendleft(node.children.values())
        while to_process:
            node = to_process.pop()
            predecessors.update(node.readers)
            if node.writer is not None:
                predecessors.add(node.writer)
            to_process.extendleft(node.children.values())

        return predecessors

    def find_read_predecessors(self, address):
        """Returns all predecessor transaction ids for a read of the provided
        address.

        Arguments:
            address (str): the radix address

        Returns: a set of transaction ids
        """
        # A read operation must be preceded by:
        #   - The "enclosing writer", which is the writer at the address or
        #     the nearest writer higher (closer to the root) in the tree.
        #   - All "children writers", which include all writers which are
        #     lower in the tree than the address.
        #
        # The enclosing writer must be added as it is possible it updated the
        # contents stored at address.
        #
        # Writers which are higher in the tree than the enclosing writer may
        # have modified the address.  However, we do not need to include them
        # here as they will have been considered a predecessor to the enclosing
        # writer.
        #
        # Children writers must be included as they may have updated addresses
        # lower in the tree, and these writers will have always been preceded
        # by the enclosing writer.
        #
        # We do not need to add any readers, since a reader cannot impact the
        # value which we are reading.  The relationship is transitive, in that
        # this reader will also not impact the readers already recorded in the
        # tree.

        tokens = self._tokenize_address(address)

        predecessors = set()

        # First, walk down from the root to the address, updating the
        # enclosing_writer if needed.

        node = self._root
        enclosing_writer = node.writer  # possibly None

        for token in tokens:
            # If the address isn't on the tree, then there aren't any
            # predecessors below the node to worry about (because
            # there isn't anything at all), so return the predecessors
            # that have already been collected.
            if token not in node.children:
                if enclosing_writer is not None:
                    predecessors.add(enclosing_writer)
                return predecessors

            node = node.children[token]

            if node.writer is not None:
                enclosing_writer = node.writer

        if enclosing_writer is not None:
            predecessors.add(enclosing_writer)

        # Next, descend down the tree starting at the address node and find
        # all children writers.  Uses breadth first search.

        to_process = deque()
        to_process.extendleft(node.children.values())
        while to_process:
            node = to_process.pop()
            if node.writer is not None:
                predecessors.add(node.writer)
            to_process.extendleft(node.children.values())

        return predecessors


class ParallelScheduler(Scheduler):
    def __init__(self, squash_handler, first_state_hash, always_persist):
        self._squash = squash_handler
        self._first_state_hash = first_state_hash
        self._last_state_hash = first_state_hash
        self._condition = Condition()
        self._predecessor_tree = PredecessorTree()
        self._txn_predecessors = {}

        self._always_persist = always_persist

        # Transaction identifiers which have been scheduled.  Stored as a list,
        # since order is important; SchedulerIterator instances, for example,
        # must all return scheduled transactions in the same order.
        self._scheduled = []

        # Transactions that must be replayed but the prior result hasn't
        # been returned yet.
        self._outstanding = set()

        # Batch id for the batch with the property that the batch doesn't have
        # all txn results, and all batches prior to it have all their txn
        # results.
        self._least_batch_id_wo_results = None

        # A dict of transaction id to TxnInformation objects, containing all
        # transactions present in self._scheduled.
        self._scheduled_txn_info = {}

        # All batches in their natural order (the order they were added to
        # the scheduler.
        self._batches = []
        # The batches that have state hashes added in add_batch, used in
        # Block validation.
        self._batches_with_state_hash = {}

        # Indexes to find a batch quickly
        self._batches_by_id = {}
        self._batches_by_txn_id = {}

        # Transaction results
        self._txn_results = {}

        self._txns_available = []
        self._transactions = {}

        self._cancelled = False
        self._final = False

    def _find_input_dependencies(self, inputs):
        """Use the predecessor tree to find dependencies based on inputs.

        Returns: A list of transaction ids.
        """
        dependencies = []
        for address in inputs:
            dependencies.extend(
                self._predecessor_tree.find_read_predecessors(address))
        return dependencies

    def _find_output_dependencies(self, outputs):
        """Use the predecessor tree to find dependencies based on outputs.

        Returns: A list of transaction ids.
        """
        dependencies = []
        for address in outputs:
            dependencies.extend(
                self._predecessor_tree.find_write_predecessors(address))
        return dependencies

    def add_batch(self, batch, state_hash=None, required=False):
        with self._condition:
            if self._final:
                raise SchedulerError('Invalid attempt to add batch to '
                                     'finalized scheduler; batch: {}'
                                     .format(batch.header_signature))
            if not self._batches:
                self._least_batch_id_wo_results = batch.header_signature

            preserve = required
            if not required:
                # If this is the first non-required batch, it is preserved for
                # the schedule to be completed (i.e. no empty schedules in the
                # event of unschedule_incomplete_batches being called before
                # the first batch is completed).
                preserve = _first(
                    filterfalse(lambda sb: sb.required,
                                self._batches_by_id.values())) is None

            self._batches.append(batch)
            self._batches_by_id[batch.header_signature] = \
                _AnnotatedBatch(batch, required=required, preserve=preserve)
            for txn in batch.transactions:
                self._batches_by_txn_id[txn.header_signature] = batch
                self._txns_available.append(txn)
                self._transactions[txn.header_signature] = txn

            if state_hash is not None:
                b_id = batch.header_signature
                self._batches_with_state_hash[b_id] = state_hash

            # For dependency handling: First, we determine our dependencies
            # based on the current state of the predecessor tree.  Second,
            # we update the predecessor tree with reader and writer
            # information based on input and outputs.
            for txn in batch.transactions:
                header = TransactionHeader()
                header.ParseFromString(txn.header)

                # Calculate predecessors (transaction ids which must come
                # prior to the current transaction).
                predecessors = self._find_input_dependencies(header.inputs)
                predecessors.extend(
                    self._find_output_dependencies(header.outputs))

                txn_id = txn.header_signature
                # Update our internal state with the computed predecessors.
                self._txn_predecessors[txn_id] = list(set(predecessors))

                # Update the predecessor tree.
                #
                # Order of reader/writer operations is relevant.  A writer
                # may overshadow a reader.  For example, if the transaction
                # has the same input/output address, the end result will be
                # this writer (txn.header_signature) stored at the address of
                # the predecessor tree.  The reader information will have been
                # discarded.  Write operations to partial addresses will also
                # overshadow entire parts of the predecessor tree.
                #
                # Thus, the order here (inputs then outputs) will cause the
                # minimal amount of relevant information to be stored in the
                # predecessor tree, with duplicate information being
                # automatically discarded by the set_writer() call.
                for address in header.inputs:
                    self._predecessor_tree.add_reader(
                        address, txn_id)
                for address in header.outputs:
                    self._predecessor_tree.set_writer(
                        address, txn_id)

            self._condition.notify_all()

    def _is_explicit_request_for_state_root(self, batch_signature):
        return batch_signature in self._batches_with_state_hash

    def _is_implicit_request_for_state_root(self, batch_signature):
        return self._final and self._is_last_valid_batch(batch_signature)

    def _is_valid_batch(self, batch):
        for txn in batch.transactions:
            if txn.header_signature not in self._txn_results:
                raise _UnscheduledTransactionError()

            result = self._txn_results[txn.header_signature]
            if not result.is_valid:
                return False
        return True

    def _is_last_valid_batch(self, batch_signature):
        batch = self._batches_by_id[batch_signature].batch
        if not self._is_valid_batch(batch):
            return False
        index_of_next = self._batches.index(batch) + 1
        for later_batch in self._batches[index_of_next:]:
            if self._is_valid_batch(later_batch):
                return False
        return True

    def _get_contexts_for_squash(self, batch_signature):
        """Starting with the batch referenced by batch_signature, iterate back
        through the batches and for each valid batch collect the context_id.
        At the end remove contexts for txns that are other txn's predecessors.

        Args:
            batch_signature (str): The batch to start from, moving back through
                the batches in the scheduler

        Returns:
            (list): Context ids that haven't been previous base contexts.
        """

        batch = self._batches_by_id[batch_signature].batch
        index = self._batches.index(batch)
        contexts = []
        txns_added_predecessors = []
        for b in self._batches[index::-1]:
            batch_is_valid = True
            contexts_from_batch = []
            for txn in b.transactions[::-1]:
                result = self._txn_results[txn.header_signature]
                if not result.is_valid:
                    batch_is_valid = False
                    break
                else:
                    txn_id = txn.header_signature
                    if txn_id not in txns_added_predecessors:
                        txns_added_predecessors.append(
                            self._txn_predecessors[txn_id])
                        contexts_from_batch.append(result.context_id)
            if batch_is_valid:
                contexts.extend(contexts_from_batch)

        return contexts

    def _is_state_hash_correct(self, state_hash, batch_id):
        return state_hash == self._batches_with_state_hash[batch_id]

    def get_batch_execution_result(self, batch_signature):
        with self._condition:
            # This method calculates the BatchExecutionResult on the fly,
            # where only the TxnExecutionResults are cached, instead
            # of BatchExecutionResults, as in the SerialScheduler
            if batch_signature not in self._batches_by_id:
                return None

            batch = self._batches_by_id[batch_signature].batch

            if not self._is_valid_batch(batch):
                return BatchExecutionResult(is_valid=False, state_hash=None)

            state_hash = None
            try:
                if self._is_explicit_request_for_state_root(batch_signature):
                    contexts = self._get_contexts_for_squash(batch_signature)
                    state_hash = self._squash(
                        self._first_state_hash,
                        contexts,
                        persist=False,
                        clean_up=False)
                    if self._is_state_hash_correct(state_hash,
                                                   batch_signature):
                        self._squash(
                            self._first_state_hash,
                            contexts,
                            persist=True,
                            clean_up=True)
                    else:
                        self._squash(
                            self._first_state_hash,
                            contexts,
                            persist=False,
                            clean_up=True)
                elif self._is_implicit_request_for_state_root(batch_signature):
                    contexts = self._get_contexts_for_squash(batch_signature)
                    state_hash = self._squash(
                        self._first_state_hash,
                        contexts,
                        persist=self._always_persist,
                        clean_up=True)
            except _UnscheduledTransactionError:
                return None

            return BatchExecutionResult(is_valid=True, state_hash=state_hash)

    def get_transaction_execution_results(self, batch_signature):
        with self._condition:
            annotated_batch = self._batches_by_id.get(batch_signature)
            if annotated_batch is None:
                return None

            results = []
            for txn in annotated_batch.batch.transactions:
                result = self._txn_results.get(txn.header_signature)
                if result is not None:
                    results.append(result)
            return results

    def _is_predecessor_of_possible_successor(self,
                                              txn_id,
                                              possible_successor):
        return txn_id in self._txn_predecessors[possible_successor]

    def _txn_has_result(self, txn_id):
        return txn_id in self._txn_results

    def _is_in_same_batch(self, txn_id_1, txn_id_2):
        return self._batches_by_txn_id[txn_id_1] == \
            self._batches_by_txn_id[txn_id_2]

    def _is_txn_to_replay(self, txn_id, possible_successor, already_seen):
        """Decide if possible_successor should be replayed.

        Args:
            txn_id (str): Id of txn in failed batch.
            possible_successor (str): Id of txn to possibly replay.
            already_seen (list): A list of possible_successors that have
                been replayed.

        Returns:
            (bool): If the possible_successor should be replayed.
        """

        is_successor = self._is_predecessor_of_possible_successor(
            txn_id,
            possible_successor)
        in_different_batch = not self._is_in_same_batch(txn_id,
                                                        possible_successor)
        has_not_been_seen = possible_successor not in already_seen

        return is_successor and in_different_batch and has_not_been_seen

    def _remove_subsequent_result_because_of_batch_failure(self, sig):
        """Remove transactions from scheduled and txn_results for
        successors of txns in a failed batch. These transactions will now,
        or in the future be rescheduled in next_transaction; giving a
        replay ability.

        Args:
            sig (str): Transaction header signature

        """

        batch = self._batches_by_txn_id[sig]
        seen = []
        for txn in batch.transactions:
            txn_id = txn.header_signature
            for poss_successor in self._scheduled.copy():
                if self._is_txn_to_replay(txn_id, poss_successor, seen):
                    if self._txn_has_result(poss_successor):
                        del self._txn_results[poss_successor]
                        self._scheduled.remove(poss_successor)
                        self._txns_available.append(
                            self._transactions[poss_successor])
                    else:
                        self._outstanding.add(poss_successor)
                    seen.append(poss_successor)

    def _reschedule_if_outstanding(self, txn_signature):
        if txn_signature in self._outstanding:
            self._txns_available.append(
                self._transactions[txn_signature])
            self._scheduled.remove(txn_signature)
            self._outstanding.discard(txn_signature)
            return True
        return False

    def _index_of_batch(self, batch):
        batch_index = None
        try:
            batch_index = self._batches.index(batch)
        except ValueError:
            pass
        return batch_index

    def _set_least_batch_id(self, txn_signature):
        """Set the first batch id that doesn't have all results.

        Args:
            txn_signature (str): The txn identifier of the transaction with
                results being set.

        """

        batch = self._batches_by_txn_id[txn_signature]

        least_index = self._index_of_batch(
            self._batches_by_id[self._least_batch_id_wo_results].batch)

        current_index = self._index_of_batch(batch)
        all_prior = False

        if current_index <= least_index:
            return
            # Test to see if all batches from the least_batch to
            # the prior batch to the current batch have results.
        if all(
                all(t.header_signature in self._txn_results
                    for t in b.transactions)
                for b in self._batches[least_index:current_index]):
            all_prior = True
        if not all_prior:
            return
        possible_least = self._batches[current_index].header_signature
        # Find the first batch from the current batch on, that doesn't have
        # all results.
        for b in self._batches[current_index:]:
            if not all(t.header_signature in self._txn_results
                       for t in b.transactions):
                possible_least = b.header_signature
                break
        self._least_batch_id_wo_results = possible_least

    def set_transaction_execution_result(
            self, txn_signature, is_valid, context_id, state_changes=None,
            events=None, data=None, error_message="", error_data=b""):
        with self._condition:
            if txn_signature not in self._scheduled:
                raise SchedulerError(
                    "transaction not scheduled: {}".format(txn_signature))

            if txn_signature not in self._batches_by_txn_id:
                return

            self._set_least_batch_id(txn_signature=txn_signature)
            if not is_valid:
                self._remove_subsequent_result_because_of_batch_failure(
                    txn_signature)
            is_rescheduled = self._reschedule_if_outstanding(txn_signature)

            if not is_rescheduled:
                self._txn_results[txn_signature] = TxnExecutionResult(
                    signature=txn_signature,
                    is_valid=is_valid,
                    context_id=context_id if is_valid else None,
                    state_hash=self._first_state_hash if is_valid else None,
                    state_changes=state_changes,
                    events=events,
                    data=data,
                    error_message=error_message,
                    error_data=error_data)

            self._condition.notify_all()

    def _unscheduled_transactions(self):

        return self._txns_available.copy()

    def _has_predecessors(self, txn):
        for predecessor_id in self._txn_predecessors[txn.header_signature]:
            if predecessor_id not in self._txn_results:
                return True
            # Since get_initial_state_for_transaction gets context ids not
            # just from predecessors but also in the case of an enclosing
            # writer failing, predecessors of that predecessor, this extra
            # check is needed.
            for pre_pred_id in self._txn_predecessors[predecessor_id]:
                if pre_pred_id not in self._txn_results:
                    return True

        return False

    def _is_outstanding(self, txn):
        return txn.header_signature in self._outstanding

    def _txn_is_in_valid_batch(self, txn_id):
        """Returns whether the transaction is in a valid batch.

        Args:
            txn_id (str): The transaction header signature.

        Returns:
            (bool): True if the txn's batch is valid, False otherwise.
        """

        batch = self._batches_by_txn_id[txn_id]

        # Return whether every transaction in the batch with a
        # transaction result is valid
        return all(
            self._txn_results[sig].is_valid
            for sig in set(self._txn_results).intersection(
                (txn.header_signature for txn in batch.transactions)))

    def _predecessor_not_in_chain(self,
                                  prior_txn_id,
                                  chain):
        """

        Args:
            prior_txn_id (str): The predecessor's txn header_signature.
            chain (list): The txn_ids whose context_ids have already been
                added.

        Returns:
            (bool): The prior_txn_id has not had its state added yet.
        """

        for pred_id in chain:
            if (prior_txn_id in self._txn_predecessors[pred_id]
                or prior_txn_id in chain) and \
                    self._txn_is_in_valid_batch(pred_id):
                return False
        return True

    def _get_initial_state_for_transaction(self, txn):
        # Collect contexts that this transaction depends upon
        # We assume that all prior txns in the batch are valid
        # or else this transaction wouldn't run. We assume that
        # the mechanism in next_transaction makes sure that each
        # predecessor txn has a result. Also any explicit
        # dependencies that could have failed this txn did so.
        contexts = []
        txn_dependencies = deque()
        predecessors = self._txn_predecessors[txn.header_signature]
        txn_dependencies.extend(self._sort_txn_ids_in_reverse(
            predecessors))
        in_chain = []
        while txn_dependencies:
            prior_txn_id = txn_dependencies.popleft()
            if self._txn_is_in_valid_batch(prior_txn_id):
                result = self._txn_results[prior_txn_id]
                if self._predecessor_not_in_chain(
                        prior_txn_id,
                        in_chain):
                    in_chain.append(prior_txn_id)
                    contexts.append(result.context_id)
            else:
                predecessors_sorted = self._sort_txn_ids_in_reverse(
                    self._txn_predecessors[prior_txn_id])
                txn_dependencies.extend(predecessors_sorted)
        return contexts

    def _sort_txn_ids_in_reverse(self, txn_ids):
        return sorted(txn_ids,
                      key=self._index_of_txn_in_schedule, reverse=True)

    def _index_of_txn_in_schedule(self, txn_id):
        batch = self._batches_by_txn_id[txn_id]
        index_of_batch_in_schedule = self._batches.index(batch)
        number_of_txns_in_prior_batches = 0
        for prior in self._batches[:index_of_batch_in_schedule]:
            number_of_txns_in_prior_batches += len(prior.transactions)

        txn_index, _ = next(
            (i, t)
            for i, t in enumerate(batch.transactions)
            if t.header_signature == txn_id)

        return number_of_txns_in_prior_batches + txn_index - 1

    def _can_fail_fast(self, txn_id):
        batch_id = self._batches_by_txn_id[txn_id].header_signature
        return batch_id == self._least_batch_id_wo_results

    def next_transaction(self):
        with self._condition:
            # We return the next transaction which hasn't been scheduled and
            # is not blocked by a dependency.

            next_txn = None
            for txn in self._unscheduled_transactions():
                if not self._has_predecessors(txn) and \
                        not self._is_outstanding(txn) and \
                        not self._dependency_not_processed(txn):
                    if self._txn_failed_by_dep(txn):
                        self._txns_available.remove(txn)
                        self._txn_results[txn.header_signature] = \
                            TxnExecutionResult(
                                signature=txn.header_signature,
                                is_valid=False,
                                context_id=None,
                                state_hash=None)
                        continue
                    txn_id = txn.header_signature
                    if not self._txn_is_in_valid_batch(txn_id) and \
                            self._can_fail_fast(txn_id):

                        self._txn_results[txn.header_signature] = \
                            TxnExecutionResult(False, None, None)
                        self._txns_available.remove(txn)
                        continue
                    next_txn = txn
                    break

            if next_txn is not None:
                bases = self._get_initial_state_for_transaction(next_txn)

                info = TxnInformation(
                    txn=next_txn,
                    state_hash=self._first_state_hash,
                    base_context_ids=bases)
                self._scheduled.append(next_txn.header_signature)
                self._txns_available.remove(next_txn)
                self._scheduled_txn_info[next_txn.header_signature] = info
                return info
            return None

    def _dependency_not_processed(self, txn):
        header = TransactionHeader()
        header.ParseFromString(txn.header)
        if any(not self._all_in_batch_have_results(d)
               for d in list(header.dependencies)
               if d in self._batches_by_txn_id):
            return True
        return False

    def _txn_failed_by_dep(self, txn):
        header = TransactionHeader()
        header.ParseFromString(txn.header)
        if any(self._any_in_batch_are_invalid(d)
               for d in list(header.dependencies)
               if d in self._batches_by_txn_id):
            return True
        return False

    def _all_in_batch_have_results(self, txn_id):
        batch = self._batches_by_txn_id[txn_id]
        return all(
            t.header_signature in self._txn_results
            for t in list(batch.transactions))

    def _any_in_batch_are_invalid(self, txn_id):
        batch = self._batches_by_txn_id[txn_id]
        return any(not self._txn_results[t.header_signature].is_valid
                   for t in list(batch.transactions))

    def available(self):
        with self._condition:
            # We return the next transaction which hasn't been scheduled and
            # is not blocked by a dependency.

            count = 0
            for txn in self._unscheduled_transactions():
                if not self._has_predecessors(txn):
                    count += 1

            return count

    def unschedule_incomplete_batches(self):
        incomplete_batches = set()
        with self._condition:
            # These transactions have never been scheduled.
            for txn in self._unscheduled_transactions():
                batch = self._batches_by_txn_id[txn.header_signature]
                batch_id = batch.header_signature

                annotated_batch = self._batches_by_id[batch_id]
                if not annotated_batch.preserve:
                    incomplete_batches.add(batch_id)

            # These transactions were in flight.
            in_flight = set(self._transactions.keys()).difference(
                self._txn_results.keys())

            for txn_id in in_flight:
                batch = self._batches_by_txn_id[txn_id]
                batch_id = batch.header_signature

                annotated_batch = self._batches_by_id[batch_id]
                if not annotated_batch.preserve:
                    incomplete_batches.add(batch_id)

            # clean up the batches, including partial complete information
            for batch_id in incomplete_batches:
                annotated_batch = self._batches_by_id[batch_id]
                self._batches.remove(annotated_batch.batch)
                del self._batches_by_id[batch_id]
                for txn in annotated_batch.batch.transactions:
                    txn_id = txn.header_signature
                    del self._batches_by_txn_id[txn_id]

                    if txn_id in self._txn_results:
                        del self._txn_results[txn_id]

                    if txn in self._txns_available:
                        self._txns_available.remove(txn)

                    if txn_id in self._outstanding:
                        self._outstanding.remove(txn_id)

            self._condition.notify_all()

        if incomplete_batches:
            LOGGER.debug('Removed %s incomplete batches from the schedule',
                         len(incomplete_batches))

    def is_transaction_in_schedule(self, txn_signature):
        with self._condition:
            return txn_signature in self._batches_by_txn_id

    def finalize(self):
        with self._condition:
            self._final = True
            self._condition.notify_all()

    def _complete(self):
        return self._final and \
            len(self._txn_results) == len(self._batches_by_txn_id)

    def complete(self, block=True):
        with self._condition:
            if self._complete():
                return True

            if block:
                return self._condition.wait_for(self._complete)

            return False

    def __del__(self):
        self.cancel()

    def __iter__(self):
        return SchedulerIterator(self, self._condition)

    def count(self):
        with self._condition:
            return len(self._scheduled)

    def get_transaction(self, index):
        with self._condition:
            return self._scheduled_txn_info[self._scheduled[index]]

    def cancel(self):
        with self._condition:
            if not self._cancelled and not self._final:
                contexts = [
                    tr.context_id for tr in self._txn_results.values()
                    if tr.context_id
                ]
                self._squash(
                    self._first_state_hash,
                    contexts,
                    persist=False,
                    clean_up=True)
                self._cancelled = True
                self._condition.notify_all()

    def is_cancelled(self):
        with self._condition:
            return self._cancelled


def _first(iterator):
    try:
        return next(iterator)
    except StopIteration:
        return None


class _UnscheduledTransactionError(Exception):
    """Thrown when information on a transaction is requested, but the
    transaction has been unscheduled.
    """
    pass

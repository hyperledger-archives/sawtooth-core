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

# pylint: disable=invalid-name

import binascii
from collections import deque
import hashlib
import itertools
import logging
import os
import time
import uuid
import yaml

from sawtooth_signing import create_context
from sawtooth_signing import CryptoFactory

from sawtooth_validator.execution.scheduler import BatchExecutionResult
from sawtooth_validator.database.native_lmdb import NativeLmdbDatabase
from sawtooth_validator.state.merkle import MerkleDatabase

from sawtooth_validator.protobuf import batch_pb2
from sawtooth_validator.protobuf import transaction_pb2


LOGGER = logging.getLogger(__name__)


def create_transaction(payload, signer, inputs=None,
                       outputs=None, dependencies=None):
    addr = '000000' + hashlib.sha512(payload).hexdigest()[:64]

    if inputs is None:
        inputs = [addr]

    if outputs is None:
        outputs = [addr]

    if dependencies is None:
        dependencies = []

    header = transaction_pb2.TransactionHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        family_name='scheduler_test',
        family_version='1.0',
        inputs=inputs,
        outputs=outputs,
        dependencies=dependencies,
        nonce=str(time.time()),
        payload_sha512=hashlib.sha512(payload).hexdigest(),
        batcher_public_key=signer.get_public_key().as_hex())

    header_bytes = header.SerializeToString()

    signature = signer.sign(header_bytes)

    transaction = transaction_pb2.Transaction(
        header=header_bytes,
        payload=payload,
        header_signature=signature)

    return transaction, header


def create_batch(transactions, signer):
    transaction_ids = [t.header_signature for t in transactions]

    header = batch_pb2.BatchHeader(
        signer_public_key=signer.get_public_key().as_hex(),
        transaction_ids=transaction_ids)

    header_bytes = header.SerializeToString()

    signature = signer.sign(header_bytes)

    batch = batch_pb2.Batch(
        header=header_bytes,
        transactions=transactions,
        header_signature=signature)

    return batch


class SchedulerTester:
    """ The canonical form of the yaml is:
      -  <------------------------------------------ batch start
        state_hash: string. Optional. No default.
        - <----------------------------------------- transaction start
          inputs: list of string. Required.
            - ....
          outputs: list of string. Required.
            - ....
          addresses_to_set: list of dict. Optional.
            - string <address>: Optional bytes <value>
          addresses_to_delete: list of str. Optional
            - string <address>
          valid: boolean. Optional. Defaults to True
          dependencies: list of string. Optional. Defaults to empty list.
            - ..... string. No default. If a dependency is the same
                            string as a 'name' for another txn, that
                            txn's signature will be used for the
                            actual Transaction's dependency. If the
                            string is not an 'name' of another txn, if
                            it is longer than 20 characters it will be
                            used as if is is the actual
                            Transaction.header_signature for the
                            dependency. If not, it will be
                            disregarded.
          name: string. Optional. No default.
    """

    def __init__(self, file_name):
        """

        Args:
            file_name (str): The yaml filename and path.
            scheduler (scheduler.Scheduler): Any Scheduler implementaion
            context_manager (context_manager.ContextManager): The context
                manager holding state for this scheduler.
        """
        self._context = create_context('secp256k1')
        self._crypto_factory = CryptoFactory(self._context)
        self._yaml_file_name = file_name
        self._counter = itertools.count(0)
        self._referenced_txns_in_other_batches = {}
        self._batch_id_by_txn_id = {}
        self._txn_execution = {}

        self._batch_results = {}
        self._batches = []

        self._create_batches()

    @property
    def batch_results(self):
        """The batch results calculated from the yaml file.

        Returns:
            (dict): Computed from the yaml file, a dictionary with
                batch signature keys and BatchExecutionResult values.
        """
        return self._batch_results

    def run_scheduler(self,
                      scheduler,
                      context_manager,
                      validation_state_hash=None,
                      txns_executed_fifo=True):
        """Add all the batches to the scheduler in order and then run through
        the txns in the scheduler, calling next_transaction() after each
        transaction_execution_result is set.

        Args:
            scheduler (scheduler.Scheduler): Any implementation of the
                Scheduler abstract base class.
            context_manager (context_manager.ContextManager): The context
                manager is needed to store state based on the yaml file.
            validation_state_hash (str): Used in cases where the yaml
                represents a single block of valid batches, and the
                state hash is not in the yaml file. This state hash is added
                to the last batch in the scheduler.

        Returns batch_results (list of tuples): A list of tuples of
            batch signature, BatchExecutionResult pairs.
        """

        for i, batch in enumerate(self._batches):
            if i == len(self._batches) - 1 and \
                    validation_state_hash is not None:
                s_h = validation_state_hash
            else:
                s_h = self._batch_results[batch.header_signature].state_hash
            scheduler.add_batch(batch=batch, state_hash=s_h)

        scheduler.finalize()
        txns_to_process = deque()

        txn_context_by_txn_id = self._compute_transaction_execution_context()

        transactions_to_assert_state = {}
        while not scheduler.complete(block=False):
            stop = False
            while not stop:
                try:
                    txn_info = scheduler.next_transaction()
                except StopIteration:
                    break
                if txn_info is not None:
                    txns_to_process.append(txn_info)
                    LOGGER.debug("Transaction %s scheduled",
                                 txn_info.txn.header_signature[:16])
                else:
                    stop = True
            try:
                if txns_executed_fifo:
                    t_info = txns_to_process.popleft()
                else:
                    t_info = txns_to_process.pop()
            except IndexError:
                # No new txn was returned from next_transaction so
                # check again if complete.
                continue

            inputs, outputs = self._get_inputs_outputs(t_info.txn)

            c_id = context_manager.create_context(
                state_hash=t_info.state_hash,
                base_contexts=t_info.base_context_ids,
                inputs=inputs,
                outputs=outputs)

            t_id = t_info.txn.header_signature

            if t_id in txn_context_by_txn_id:
                state_up_to_now = txn_context_by_txn_id[t_id].state
                txn_context = txn_context_by_txn_id[t_id]
                inputs, _ = self._get_inputs_outputs(txn_context.txn)
                addresses = [input for input in inputs if len(input) == 70]
                state_found = context_manager.get(
                    context_id=c_id,
                    address_list=addresses)

                LOGGER.debug("Transaction Id %s, Batch %s, Txn %s, "
                             "Context_id %s, Base Contexts %s",
                             t_id[:16],
                             txn_context.batch_num,
                             txn_context.txn_num,
                             c_id,
                             t_info.base_context_ids)

                state_to_assert = [(add, state_up_to_now.get(add))
                                   for add, _ in state_found]
                transactions_to_assert_state[t_id] = (txn_context,
                                                      state_found,
                                                      state_to_assert)

            validity, address_values, deletes = self._txn_execution[
                t_info.txn.header_signature]

            context_manager.set(
                context_id=c_id,
                address_value_list=address_values)

            context_manager.delete(
                context_id=c_id,
                address_list=deletes)
            LOGGER.debug("Transaction %s is %s",
                         t_id[:16],
                         'valid' if validity else 'invalid')
            scheduler.set_transaction_execution_result(
                txn_signature=t_info.txn.header_signature,
                is_valid=validity,
                context_id=c_id)

        batch_ids = [b.header_signature for b in self._batches]
        batch_results = [
            (b_id, scheduler.get_batch_execution_result(b_id))
            for b_id in batch_ids]

        return batch_results, transactions_to_assert_state

    def run_scheduler_alternating(self, scheduler, context_manager,
                                  validation_state_hash=None,
                                  txns_executed_fifo=True):
        batches = deque()
        batches.extend(self._batches)

        txns_to_process = deque()

        txn_context_by_txn_id = self._compute_transaction_execution_context()

        transactions_to_assert_state = {}
        while not scheduler.complete(block=False):
            stop = False
            while not stop:
                try:
                    txn_info = scheduler.next_transaction()
                except StopIteration:
                    stop = True

                if txn_info is not None:
                    txns_to_process.append(txn_info)
                    LOGGER.debug("Transaction %s scheduled",
                                 txn_info.txn.header_signature[:16])
                else:
                    stop = True

            try:
                scheduler.add_batch(batches.popleft())
            except IndexError:
                scheduler.finalize()

            try:
                if txns_executed_fifo:
                    t_info = txns_to_process.popleft()
                else:
                    t_info = txns_to_process.pop()
            except IndexError:
                # No new txn was returned from next_transaction so
                # check again if complete.
                continue

            inputs, outputs = self._get_inputs_outputs(t_info.txn)

            c_id = context_manager.create_context(
                state_hash=t_info.state_hash,
                base_contexts=t_info.base_context_ids,
                inputs=inputs,
                outputs=outputs)

            t_id = t_info.txn.header_signature

            if t_id in txn_context_by_txn_id:
                state_up_to_now = txn_context_by_txn_id[t_id].state
                txn_context = txn_context_by_txn_id[t_id]
                inputs, _ = self._get_inputs_outputs(txn_context.txn)
                addresses = [input for input in inputs if len(input) == 70]
                state_found = context_manager.get(
                    context_id=c_id,
                    address_list=addresses)

                LOGGER.debug("Transaction Id %s, Batch %s, Txn %s, "
                             "Context_id %s, Base Contexts %s",
                             t_id[:16],
                             txn_context.batch_num,
                             txn_context.txn_num,
                             c_id,
                             t_info.base_context_ids)

                state_to_assert = [(add, state_up_to_now.get(add))
                                   for add, _ in state_found]
                transactions_to_assert_state[t_id] = (txn_context,
                                                      state_found,
                                                      state_to_assert)

            validity, address_values, deletes = self._txn_execution[
                t_info.txn.header_signature]

            context_manager.set(
                context_id=c_id,
                address_value_list=address_values)
            context_manager.delete(
                context_id=c_id,
                address_list=deletes)
            LOGGER.debug("Transaction %s is %s",
                         t_id[:16],
                         'valid' if validity else 'invalid')
            scheduler.set_transaction_execution_result(
                txn_signature=t_info.txn.header_signature,
                is_valid=validity,
                context_id=c_id)

        batch_ids = [b.header_signature for b in self._batches]
        batch_results = [
            (b_id, scheduler.get_batch_execution_result(b_id))
            for b_id in batch_ids]

        return batch_results, transactions_to_assert_state

    def compute_state_hashes_wo_scheduler(self, base_dir):
        """Creates a state hash from the state updates from each txn in a
        valid batch.

        Returns state_hashes (list of str): The merkle roots from state
            changes in 1 or more blocks in the yaml file.

        """

        database = NativeLmdbDatabase(
            os.path.join(base_dir, 'compute_state_hashes_wo_scheduler.lmdb'),
            indexes=MerkleDatabase.create_index_configuration(),
            _size=10 * 1024 * 1024)

        tree = MerkleDatabase(database=database)
        state_hashes = []
        updates = {}
        for batch in self._batches:
            b_id = batch.header_signature
            result = self._batch_results[b_id]
            if result.is_valid:
                for txn in batch.transactions:
                    txn_id = txn.header_signature
                    _, address_values, deletes = self._txn_execution[txn_id]
                    batch_updates = {}
                    for pair in address_values:
                        batch_updates.update({a: pair[a] for a in pair.keys()})

                    # since this is entirely serial, any overwrite
                    # of an address is expected and desirable.
                    updates.update(batch_updates)

                    for address in deletes:
                        if address in updates:
                            del updates[address]

            # This handles yaml files that have state roots in them
            if result.state_hash is not None:
                s_h = tree.update(set_items=updates, virtual=False)
                tree.set_merkle_root(merkle_root=s_h)
                state_hashes.append(s_h)
        if not state_hashes:
            state_hashes.append(tree.update(set_items=updates))
        return state_hashes

    def _compute_transaction_execution_context(self):
        """Compute the serial state for each txn in the yaml file up to and
        including the invalid txn in each invalid batch.

        Notes:
            The TransactionExecutionContext for a txn will contain the
            state applied serially up to that point for each valid batch and
            then for invalid batches up to the invalid txn.

        Returns:
            dict: The transaction id to the TransactionExecutionContext
        """
        transaction_contexts = {}
        state_up_to_now = {}

        for batch_num, batch in enumerate(self._batches):
            partial_batch_transaction_contexts = {}
            partial_batch_state_up_to_now = state_up_to_now.copy()
            for txn_num, txn in enumerate(batch.transactions):
                t_id = txn.header_signature
                is_valid, address_values, deletes = self._txn_execution[t_id]
                partial_batch_transaction_contexts[t_id] = \
                    TransactionExecutionContext(
                        txn=txn,
                        txn_num=txn_num + 1,
                        batch_num=batch_num + 1,
                        state=partial_batch_state_up_to_now.copy())

                for item in address_values:
                    partial_batch_state_up_to_now.update(item)
                for address in deletes:
                    if address in partial_batch_state_up_to_now:
                        partial_batch_state_up_to_now[address] = None
                if not is_valid:
                    break
            batch_id = batch.header_signature
            batch_is_valid = self._batch_results[batch_id].is_valid

            if batch_is_valid:
                transaction_contexts.update(partial_batch_transaction_contexts)
                state_up_to_now.update(partial_batch_state_up_to_now)

        return transaction_contexts

    def _address(self, add, require_full=False):
        if ':sha' not in add and ',' not in add:
            return add

        if ',' in add:
            return binascii.hexlify(bytearray(
                [int(i) for i in add.split(',')]))

        parts = add.split(':')
        if len(parts) == 3 and parts[2] == 'sha':
            # eg. 'yy:aaabbbb:sha'
            namespace = hashlib.sha512(parts[0].encode()).hexdigest()[:6]
            address = namespace + hashlib.sha512(
                parts[1].encode()).hexdigest()[:64]
        elif len(parts) == 3 and not require_full:
            # eg. 'a:sha:56'
            length = min(int(parts[2]), 70)
            address = hashlib.sha512(parts[0].encode()).hexdigest()[:length]
        elif len(parts) == 2:
            # eg. 'aaabbbb:sha'
            intermediate = parts[0]
            address = hashlib.sha512(intermediate.encode()).hexdigest()[:70]
        else:
            raise ValueError("Address specified by {} could "
                             "not be formed".format(add))
        return address

    def _get_inputs_outputs(self, txn):
        """Similarly to the TransactionExecutor, deserialize the inputs and
         outputs.

         Notes:
             The SchedulerTester has the inputs and outputs from the yaml file
             that it used to create the transaction, but it seems less
             error-prone to recreate the behavior of the TransactionExecutor.

        Args:
            txn (sawtooth_validator.protobuf.transaction_pb2.Transaction)

        Returns (tuple): (inputs, outputs)

        """

        header = transaction_pb2.TransactionHeader()
        header.ParseFromString(txn.header)

        return list(header.inputs), list(header.outputs)

    def _bytes_if_none(self, value):
        if value is None:
            value = uuid.uuid4().hex.encode()
        return value

    def _yaml_from_file(self):
        with open(self._yaml_file_name, 'r') as infile:
            test_yaml = yaml.safe_load(infile)
        return test_yaml

    def _contains_and_not_none(self, key, obj):
        return key in obj and obj[key] is not None

    def _process_batches(self, yaml_batches, signer):
        batches = []
        b_results = {}
        for batch in yaml_batches:
            batch_state_root = None
            if self._contains_and_not_none('state_hash', batch):
                batch_state_root = batch['state_hash']

            txn_processing_result = self._process_txns(
                batch=batch,
                previous_batch_results=b_results.copy(),
                signer=signer)
            txns, batch_is_valid = txn_processing_result
            batch_real = create_batch(
                transactions=txns,
                signer=signer)
            for txn in txns:
                txn_id = txn.header_signature
                batch_id = batch_real.header_signature
                self._batch_id_by_txn_id[txn_id] = batch_id

            b_results[batch_real.header_signature] = BatchExecutionResult(
                is_valid=batch_is_valid,
                state_hash=batch_state_root)
            batches.append(batch_real)
        return batches, b_results

    def _dependencies_are_valid(self, dependencies, previous_batch_results):
        for dep in dependencies:
            if dep in self._batch_id_by_txn_id:
                batch_id = self._batch_id_by_txn_id[dep]
                dep_result = previous_batch_results[batch_id]
                if not dep_result.is_valid:
                    return False
        return True

    def _process_txns(self, batch, previous_batch_results, signer):
        txns = []
        referenced_txns = {}
        execution = {}
        batch_is_valid = True
        for transaction in batch:
            is_valid = True
            addresses_to_set = []
            addresses_to_delete = []
            inputs = transaction['inputs']
            outputs = transaction['outputs']
            inputs_real = [self._address(a) for a in inputs]
            outputs_real = [self._address(a) for a in outputs]
            if self._contains_and_not_none('addresses_to_set', transaction):
                addresses_to_set = [{
                    self._address(a, require_full=True): self._bytes_if_none(
                        d[a])
                    for a in d
                } for d in transaction['addresses_to_set']]
            if self._contains_and_not_none('addresses_to_delete', transaction):
                addresses_to_delete = [
                    self._address(a, require_full=True)
                    for a in transaction['addresses_to_delete']
                ]

            if self._contains_and_not_none('dependencies', transaction):
                if any([
                        a not in self._referenced_txns_in_other_batches
                        and len(a) <= 20 for a in transaction['dependencies']
                ]):
                    # This txn has a dependency with a txn signature that is
                    # not known about,
                    return None

                dependencies = [
                    self._referenced_txns_in_other_batches[a]
                    if a in self._referenced_txns_in_other_batches else a
                    for a in transaction['dependencies']
                ]
                dependencies = [a for a in dependencies if len(a) > 20]
            else:
                dependencies = []

            deps_valid = self._dependencies_are_valid(
                dependencies,
                previous_batch_results)

            if self._contains_and_not_none('valid', transaction):
                is_valid = bool(transaction['valid'])

            if not is_valid or not deps_valid:
                batch_is_valid = False

            txn, _ = create_transaction(
                payload=uuid.uuid4().hex.encode(),
                dependencies=dependencies,
                inputs=inputs_real,
                outputs=outputs_real,
                signer=signer)

            if self._contains_and_not_none('name', transaction):
                referenced_txns[transaction['name']] = txn.header_signature

            execution[txn.header_signature] = (is_valid,
                                               addresses_to_set,
                                               addresses_to_delete)
            txns.append(txn)

        self._txn_execution.update(execution)
        self._referenced_txns_in_other_batches.update(referenced_txns)
        return txns, batch_is_valid

    def _create_batches(self):
        test_yaml = self._yaml_from_file()
        private_key = self._context.new_random_private_key()
        signer = self._crypto_factory.new_signer(private_key)

        batches, batch_results = self._process_batches(
            yaml_batches=test_yaml,
            signer=signer)

        self._batch_results = batch_results
        self._batches = batches


class TransactionExecutionContext:
    """The state for a particular transaction built up serially based
    on the Yaml file.
    """

    def __init__(self,
                 txn,
                 txn_num,
                 batch_num,
                 state):
        """

        Args:
            txn (Transaction): The transaction
            txn_num (int): The placement of the txn in the batch
            batch_num (int): The placement of the batch in the scheduler
            state (dict): The bytes at an address in state.
        """

        self.txn = txn
        self.txn_num = txn_num
        self.batch_num = batch_num
        self.state = state

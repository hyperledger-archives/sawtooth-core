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

import binascii
from collections import deque
from collections import namedtuple
import copy
import hashlib
import itertools
import logging
import time
import uuid
import yaml

import sawtooth_signing as signing

from sawtooth_validator.database.dict_database import DictDatabase
from sawtooth_validator.execution.scheduler import BatchExecutionResult
from sawtooth_validator.state.merkle import MerkleDatabase

import sawtooth_validator.protobuf.batch_pb2 as batch_pb2
import sawtooth_validator.protobuf.transaction_pb2 as transaction_pb2


LOGGER = logging.getLogger(__name__)


# Used in creating batches from the yaml file and keeping the
# ordering specified in the yaml file.
UnProcessedBatchInfo = namedtuple('UnprocessedBatchInfo',
                                  ['batch', 'key'])


def create_transaction(payload, private_key, public_key, inputs=None,
                        outputs=None, dependencies=None):
    addr = '000000' + hashlib.sha512(payload).hexdigest()[:64]

    if inputs is None:
        inputs = [addr]

    if outputs is None:
        outputs = [addr]

    if dependencies is None:
        dependencies = []

    header = transaction_pb2.TransactionHeader(
        signer_pubkey=public_key,
        family_name='scheduler_test',
        family_version='1.0',
        inputs=inputs,
        outputs=outputs,
        dependencies=dependencies,
        nonce=str(time.time()),
        payload_encoding="application/cbor",
        payload_sha512=hashlib.sha512(payload).hexdigest(),
        batcher_pubkey=public_key)

    header_bytes = header.SerializeToString()

    signature = signing.sign(header_bytes, private_key)

    transaction = transaction_pb2.Transaction(
        header=header_bytes,
        payload=payload,
        header_signature=signature)

    return transaction, header


def create_batch(transactions, private_key, public_key):
    transaction_ids = [t.header_signature for t in transactions]

    header = batch_pb2.BatchHeader(
        signer_pubkey=public_key,
        transaction_ids=transaction_ids)

    header_bytes = header.SerializeToString()

    signature = signing.sign(header_bytes, private_key)

    batch = batch_pb2.Batch(
        header=header_bytes,
        transactions=transactions,
        header_signature=signature)

    return batch


class SchedulerTester(object):
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
          valid: boolean. Optional. Defaults to True
          dependencies: list of string. Optional. Defaults to empty list.
            - ..... string. No default. If a dependency is the
                            same string as an 'id' for another txn, that txn's
                            signature will be used for the actual Transaction's
                            dependency. If the string is not an 'id' of another
                            txn, if it is longer than 20 characters it will be
                            used as if is is the actual
                            Transaction.header_signature for the dependency.
                            If not, it will be disregarded.
         id: string. Optional. No default."""

    def __init__(self, file_name):
        """

        Args:
            file_name (str): The yaml filename and path.
            scheduler (scheduler.Scheduler): Any Scheduler implementaion
            context_manager (context_manager.ContextManager): The context
                manager holding state for this scheduler.
        """
        self._yaml_file_name = file_name
        self._counter = itertools.count(0)
        self._referenced_txns_in_other_batches = {}
        # txn.header_signature : (is_valid, [{add: bytes}
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
        while not scheduler.complete(block=False):
            stop = False
            while not stop:
                txn_info = scheduler.next_transaction()
                if txn_info is not None:
                    txns_to_process.append(txn_info)
                else:
                    stop = True

            if txns_executed_fifo:
                t_info = txns_to_process.popleft()
            else:
                t_info = txns_to_process.pop()

            inputs, outputs = self._get_inputs_outputs(t_info.txn)

            c_id = context_manager.create_context(
                state_hash=t_info.state_hash,
                base_contexts=t_info.base_context_ids,
                inputs=inputs,
                outputs=outputs)
            validity_of_transaction, address_values = self._txn_execution[
                t_info.txn.header_signature]

            context_manager.set(
                context_id=c_id,
                address_value_list=address_values)

            if validity_of_transaction is False:
                context_manager.delete_contexts(
                    context_id_list=[c_id])
            scheduler.set_transaction_execution_result(
                txn_signature=t_info.txn.header_signature,
                is_valid=validity_of_transaction,
                context_id=c_id)

        batch_ids = [b.header_signature for b in self._batches]
        batch_results = [
            (b_id, scheduler.get_batch_execution_result(b_id))
            for b_id in batch_ids]
        return batch_results

    def compute_state_hashes_wo_scheduler(self):
        """Creates a state hash from the state updates from each txn in a
        valid batch.

        Returns state_hashes (list of str): The merkle roots from state
            changes in 1 or more blocks in the yaml file.

        """

        tree = MerkleDatabase(database=DictDatabase())
        state_hashes = []
        updates = {}
        for batch in self._batches:
            b_id = batch.header_signature
            result = self._batch_results[b_id]
            if result.is_valid:
                for txn in batch.transactions:
                    txn_id = txn.header_signature
                    _, address_values = self._txn_execution[txn_id]
                    batch_updates = {}
                    for pair in address_values:
                        batch_updates.update({a: pair[a] for a in pair.keys()})
                    # since this is entirely serial, any overwrite
                    # of an address is expected and desirable.
                    updates.update(batch_updates)
            # This handles yaml files that have state roots in them
            if result.state_hash is not None:
                s_h = tree.update(set_items=updates, virtual=False)
                tree.set_merkle_root(merkle_root=s_h)
                state_hashes.append(s_h)
        if not state_hashes:
            state_hashes.append(tree.update(set_items=updates))
        return state_hashes

    def _address(self, add, require_full=False):
        if ':sha' not in add and ',' not in add:
            return add

        if ',' in add:
            return binascii.hexlify(bytearray(
                [int(i) for i in add.split(',')]))

        parts = add.split(':')
        assert parts[0] is not '', "{} is not correctly specified".format(add)
        if len(parts) > 2 and not require_full:
            # eg. 'aaabbbb:sha:56'
            length = min(int(parts[2]), 70)
            intermediate = parts[0]
            address = hashlib.sha512(
                intermediate.encode()).hexdigest()[:length]
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

    def _unique_integer_key(self):
        return next(self._counter)

    def _contains_and_not_none(self, key, obj):
        return key in obj and obj[key] is not None

    def _process_prev_batches(self,
                              unprocessed_batches,
                              priv_key,
                              pub_key,
                              strip_deps=False):
        batches = []
        batches_waiting = []
        b_results = {}
        for batch_info in unprocessed_batches:
            batch = batch_info.batch
            key = batch_info.key
            batch_state_root = None
            if self._contains_and_not_none('state_hash', batch):
                batch_state_root = batch['state_hash']
            if 'state_hash' in batch:  # here we don't care if it is None
                del batch['state_hash']

            txn_processing_result = self._process_txns(
                batch=batch,
                priv_key=priv_key,
                pub_key=pub_key,
                strip_deps=strip_deps)
            if txn_processing_result is None:
                batches_waiting.append(batch_info)

            else:
                txns, batch_is_valid = txn_processing_result
                batch_real = create_batch(
                    transactions=txns,
                    private_key=priv_key,
                    public_key=pub_key)
                b_results[batch_real.header_signature] = BatchExecutionResult(
                    is_valid=batch_is_valid,
                    state_hash=batch_state_root)
                batches.append((batch_real, key))
        return batches, b_results, batches_waiting

    def _process_batches(self, yaml_batches, priv_key, pub_key):
        batches = []
        batches_waiting = []
        b_results = {}
        for batch in yaml_batches:
            batch_state_root = None
            batch_dict = None
            if self._contains_and_not_none('state_hash', batch):
                batch_state_root = batch['state_hash']

            if 'state_hash' in batch:  # here we don't care if it is None
                batch_dict = copy.copy(batch)
                del batch['state_hash']

            txn_processing_result = self._process_txns(
                batch=batch,
                priv_key=priv_key,
                pub_key=pub_key)
            if txn_processing_result is None:
                key = self._unique_integer_key()
                batches.append(key)
                waiting_batch = UnProcessedBatchInfo(
                    batch=batch_dict if batch_dict is not None else batch,
                    key=key)
                batches_waiting.append(waiting_batch)
            else:
                txns, batch_is_valid = txn_processing_result
                batch_real = create_batch(
                    transactions=txns,
                    private_key=priv_key,
                    public_key=pub_key)
                b_results[batch_real.header_signature] = BatchExecutionResult(
                    is_valid=batch_is_valid,
                    state_hash=batch_state_root)
                batches.append(batch_real)
        return batches, b_results, batches_waiting

    def _process_txns(self, batch, priv_key, pub_key, strip_deps=False):
        txns = []
        referenced_txns = {}
        execution = {}
        batch_is_valid = True
        for transaction in batch:
            is_valid = True
            addresses_to_set = []
            inputs = transaction['inputs']
            outputs = transaction['outputs']
            inputs_real = [self._address(a) for a in inputs]
            outputs_real = [self._address(a) for a in outputs]
            if self._contains_and_not_none('addresses_to_set', transaction):
                addresses_to_set = [
                    {self._address(a, require_full=True): self._bytes_if_none(
                        d[a])
                        for a in d}
                    for d in transaction['addresses_to_set']
                ]

            if self._contains_and_not_none('valid', transaction):
                is_valid = bool(transaction['valid'])
            if not is_valid:
                batch_is_valid = False

            if self._contains_and_not_none('dependencies', transaction) and \
                    not strip_deps:
                if any([a not in self._referenced_txns_in_other_batches and
                        len(a) <= 20 for a in transaction['dependencies']]):
                    # This txn has a dependency with a txn signature that is
                    # not known about, so delay processing this batch.
                    return None

                dependencies = [
                    self._referenced_txns_in_other_batches[a]
                    if a in self._referenced_txns_in_other_batches else a
                    for a in transaction['dependencies']]
                dependencies = [a for a in dependencies if len(a) > 20]
            else:
                dependencies = []

            txn, _ = create_transaction(
                payload=uuid.uuid4().hex.encode(),
                dependencies=dependencies,
                inputs=inputs_real,
                outputs=outputs_real,
                private_key=priv_key,
                public_key=pub_key)

            if self._contains_and_not_none('name', transaction):
                referenced_txns[transaction['name']] = txn.header_signature

            execution[txn.header_signature] = (is_valid, addresses_to_set)
            txns.append(txn)

        self._txn_execution.update(execution)
        self._referenced_txns_in_other_batches.update(referenced_txns)
        return txns, batch_is_valid

    def _create_batches(self):
        test_yaml = self._yaml_from_file()
        priv_key = signing.generate_privkey()
        pub_key = signing.generate_pubkey(priv_key)

        batches, batch_results, batches_waiting = self._process_batches(
            yaml_batches=test_yaml,
            priv_key=priv_key,
            pub_key=pub_key)
        # if there aren't any explicit dependencies that need to be created
        # based on the transaction 'id' listed in the yaml, the next two
        # code blocks won't be run.
        while batches_waiting:
            b, b_r, b_w = self._process_prev_batches(
                unprocessed_batches=batches_waiting,
                priv_key=priv_key,
                pub_key=pub_key)
            if len(batches_waiting) == len(b_w):
                # If any process attempt doesn't produce a new batch,
                # there is probably a cyclic dependency
                break
            if b:
                for batch, key in b:
                    ind = batches.index(key)
                    batches[ind] = batch
                batch_results.update(b_r)
            batches_waiting = b_w
        # Here process the batches with transaction dependencies that can't
        # be computed for some reason, so just strip them out.
        if batches_waiting:
            b, b_r, b_w = self._process_prev_batches(
                batches_waiting,
                priv_key=priv_key,
                pub_key=pub_key,
                strip_deps=True)
            for batch, key in b:
                ind = batches.index(key)
                batches[ind] = batch
            batch_results.update(b_r)

        self._batch_results = batch_results
        self._batches = batches

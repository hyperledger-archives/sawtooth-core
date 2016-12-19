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
import random
import string
import threading

from sawtooth_validator.protobuf import processor_pb2
from sawtooth_validator.protobuf import transaction_pb2
from sawtooth_validator.protobuf import validator_pb2


def _generate_id():
    return hashlib.sha512(''.join(
        [random.choice(string.ascii_letters)
            for _ in range(0, 1024)]).encode()).hexdigest()


class TransactionExecutorThread(threading.Thread):
    def __init__(self, service, context_manager, last_state_root, scheduler):
        super(TransactionExecutorThread, self).__init__()

        self._service = service
        self._context_manager = context_manager
        self._scheduler = scheduler

        self._last_state_root = last_state_root
        self._context_id = None

    def run(self):
        txns_valid = []
        for txn_info in self._scheduler:
            txn = txn_info.txn
            header = transaction_pb2.TransactionHeader()
            header.ParseFromString(txn.header)

            context_id = self._context_manager.create_context(
                self._last_state_root,
                inputs=list(header.inputs),
                outputs=list(header.outputs))
            content = processor_pb2.TransactionProcessRequest(
                header=txn.header,
                payload=txn.payload,
                signature=txn.signature,
                context_id=context_id).SerializeToString()

            message = validator_pb2.Message(
                message_type='tp/process',
                correlation_id=_generate_id(),
                content=content)

            future = self._service.send_txn(header=header, message=message)
            response = processor_pb2.TransactionProcessResponse()
            response.ParseFromString(future.result().content)
            if response.status == processor_pb2.TransactionProcessResponse.OK:
                txns_valid.append(True)
                if txn_info.new_state_hash:
                    self._last_state_root = self._context_manager.\
                        commit_context(context_id_list=[context_id],
                                       virtual=False)
            else:
                txns_valid.append(False)
                self._context_manager.delete_context(
                    context_id_list=[context_id])
            if txn_info.inform:
                valid = all(txns_valid)
                if valid:
                    self._scheduler.set_status(
                        txn.signature,
                        valid,
                        self._last_state_root)
                else:
                    self._scheduler.set_status(txn.signature, valid)
                txns_valid = []
            print("Last Root ", self._last_state_root)
            assert self._last_state_root is not None

            self._scheduler.mark_as_applied(txn.signature)


class TransactionExecutor(object):
    def __init__(self, service, context_manager):
        self._service = service
        self._context_manager = context_manager
        self._last_state_root = context_manager.get_first_root()

    def execute(self, scheduler, state_hash=None):
        if state_hash is not None:
            self._last_state_root = state_hash
        t = TransactionExecutorThread(self._service,
                                      self._context_manager,
                                      self._last_state_root,
                                      scheduler)
        t.start()

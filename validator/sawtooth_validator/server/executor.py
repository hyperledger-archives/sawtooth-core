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

from sawtooth_validator.scheduler.serial import SerialScheduler


def _generate_id():
    return hashlib.sha512(''.join(
        [random.choice(string.ascii_letters)
            for _ in range(0, 1024)]).encode()).hexdigest()


class TransactionExecutorThread(threading.Thread):
    def __init__(self, service, context_manager, scheduler):
        super(TransactionExecutorThread, self).__init__()

        self._service = service
        self._context_manager = context_manager
        self._scheduler = scheduler

    def _future_done_callback(self, request, result):
        """

        :param request (bytes):the serialized request
        :param result (FutureResult):
        """
        req = processor_pb2.TransactionProcessRequest()
        req.ParseFromString(request)

        response = processor_pb2.TransactionProcessResponse()
        response.ParseFromString(result.content)
        if response.status == processor_pb2.TransactionProcessResponse.OK:
            self._scheduler.set_status(req.signature, True, req.context_id)
        else:
            self._context_manager.delete_context(
                context_id_list=[req.context_id])
            self._scheduler.set_status(req.signature, False, req.context_id)

    def run(self):
        for txn_info in self._scheduler:
            txn = txn_info.txn
            header = transaction_pb2.TransactionHeader()
            header.ParseFromString(txn.header)

            context_id = self._context_manager.create_context(
                txn_info.state_hash,
                inputs=list(header.inputs),
                outputs=list(header.outputs))
            content = processor_pb2.TransactionProcessRequest(
                header=txn.header,
                payload=txn.payload,
                signature=txn.header_signature,
                context_id=context_id).SerializeToString()

            message = validator_pb2.Message(
                message_type='tp/process',
                correlation_id=_generate_id(),
                content=content)

            future = self._service.send_txn(header=header, message=message)
            future.add_callback(self._future_done_callback)


class TransactionExecutor(object):
    def __init__(self, service, context_manager):
        self._service = service
        self._context_manager = context_manager

    def create_scheduler(self, squash_handler, first_state_root):
        return SerialScheduler(squash_handler, first_state_root)

    def execute(self, scheduler):
        t = TransactionExecutorThread(self._service,
                                      self._context_manager,
                                      scheduler)
        t.start()

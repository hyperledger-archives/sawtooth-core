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
import threading

from sawtooth_validator.protobuf import processor_pb2
from sawtooth_validator.protobuf import transaction_pb2
from sawtooth_validator.protobuf import validator_pb2

from sawtooth_validator.execution.scheduler_serial import SerialScheduler
from sawtooth_validator.execution import processor_iterator


LOGGER = logging.getLogger(__name__)


class TransactionExecutorThread(threading.Thread):
    def __init__(self, service, context_manager, scheduler, processors,
                 require_txn_processors=False):
        super(TransactionExecutorThread, self).__init__()
        self._service = service
        self._context_manager = context_manager
        self._scheduler = scheduler
        self._processors = processors
        self._require_txn_processors = require_txn_processors

    def _future_done_callback(self, request, result):
        """
        :param request (bytes):the serialized request
        :param result (FutureResult):
        """
        req = processor_pb2.TpProcessRequest()
        req.ParseFromString(request)

        response = processor_pb2.TpProcessResponse()
        response.ParseFromString(result.content)
        if response.status == processor_pb2.TpProcessResponse.OK:
            self._scheduler.set_transaction_execution_result(
                req.signature, True, req.context_id)
        else:
            self._context_manager.delete_context(
                context_id_list=[req.context_id])
            self._scheduler.set_transaction_execution_result(
                req.signature, False, req.context_id)

    def run(self):
        for txn_info in self._scheduler:
            txn = txn_info.txn
            header = transaction_pb2.TransactionHeader()
            header.ParseFromString(txn.header)

            context_id = self._context_manager.create_context(
                txn_info.state_hash,
                inputs=list(header.inputs),
                outputs=list(header.outputs))
            content = processor_pb2.TpProcessRequest(
                header=txn.header,
                payload=txn.payload,
                signature=txn.header_signature,
                context_id=context_id).SerializeToString()

            processor_type = processor_iterator.ProcessorType(
                header.family_name,
                header.family_version,
                header.payload_encoding)

            # Currently we only check for the sawtooth_config txn family,
            # as it is the only family we know to require.
            if self._require_txn_processors and \
                    header.family_name == 'sawtooth_config' and \
                    processor_type not in self._processors:
                # wait until required processor is registered:
                LOGGER.info('Waiting for transaction processor (%s, %s, %s)',
                            header.family_name,
                            header.family_version,
                            header.payload_encoding)

                self._processors.wait_to_process(processor_type)

            if processor_type not in self._processors:
                raise Exception("internal error, no processor available")
            processor = self._processors.get_next_of_type(processor_type)
            identity = processor.identity

            future = self._service.send(
                validator_pb2.Message.TP_PROCESS_REQUEST,
                content,
                identity=identity,
                has_callback=True)
            future.add_callback(self._future_done_callback)


class TransactionExecutor(object):
    def __init__(self, service, context_manager):
        self._service = service
        self._context_manager = context_manager
        self.processors = processor_iterator.ProcessorIteratorCollection(
            processor_iterator.RoundRobinProcessorIterator)

    def create_scheduler(self, squash_handler, first_state_root):
        return SerialScheduler(squash_handler, first_state_root)

    def execute(self, scheduler, require_txn_processors=False):
        t = TransactionExecutorThread(
            self._service,
            self._context_manager,
            scheduler,
            self.processors,
            require_txn_processors=require_txn_processors)
        t.start()

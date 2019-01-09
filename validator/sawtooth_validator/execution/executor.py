# Copyright 2016, 2017 Intel Corporation
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
import json
import logging
import threading

from sawtooth_validator.protobuf import processor_pb2
from sawtooth_validator.protobuf import network_pb2
from sawtooth_validator.protobuf import transaction_pb2
from sawtooth_validator.protobuf import validator_pb2
from sawtooth_validator.protobuf import transaction_receipt_pb2
from sawtooth_validator.exceptions import WaitCancelledException

from sawtooth_validator.concurrent.threadpool import \
    InstrumentedThreadPoolExecutor
from sawtooth_validator.execution.context_manager import \
    CreateContextException
from sawtooth_validator.execution.scheduler_serial import SerialScheduler
from sawtooth_validator.execution.scheduler_parallel import ParallelScheduler
from sawtooth_validator.execution.processor_manager import ProcessorType
from sawtooth_validator.execution.processor_manager import ProcessorManager
from sawtooth_validator.execution.processor_manager import \
    RoundRobinProcessorIterator
from sawtooth_validator.networking.future import FutureResult
from sawtooth_validator.networking.future import FutureTimeoutError
from sawtooth_validator import metrics

LOGGER = logging.getLogger(__name__)
COLLECTOR = metrics.get_collector(__name__)


class TransactionExecutorThread:
    """A thread of execution controlled by the TransactionExecutor.
    Provides the functionality that the journal can process on several
    schedulers at once.
    """

    def __init__(self,
                 service,
                 context_manager,
                 scheduler,
                 processor_manager,
                 settings_view_factory,
                 invalid_observers):
        """
        Args:
            service (Interconnect): The zmq internal interface
            context_manager (ContextManager): The cached state for tps
            scheduler (scheduler.Scheduler): Provides the order of txns to
                execute.
            processor_manager (ProcessorManager): Provides the next
                transaction processor to send to.
            settings_view_factory (SettingsViewFactory): Read the configuration
                state
        Attributes:
            _tp_settings_key (str): the key used to reference the part of state
                where the list of required transaction processors are.
        """
        super(TransactionExecutorThread, self).__init__()
        self._service = service
        self._context_manager = context_manager
        self._scheduler = scheduler
        self._processor_manager = processor_manager
        self._settings_view_factory = settings_view_factory
        self._tp_settings_key = "sawtooth.validator.transaction_families"
        self._done = False
        self._invalid_observers = invalid_observers
        self._open_futures = {}

        self._tp_process_response_counters = {}
        self._transaction_execution_count = COLLECTOR.counter(
            'transaction_execution_count', instance=self)
        self._in_process_transactions_count = COLLECTOR.counter(
            'in_process_transactions_count', instance=self)

    def _get_tp_process_response_counter(self, tag):
        if tag not in self._tp_process_response_counters:
            self._tp_process_response_counters[tag] = COLLECTOR.counter(
                'tp_process_response_count',
                tags={'response_type': tag},
                instance=self)
        return self._tp_process_response_counters[tag]

    def _future_done_callback(self, request, result):
        """
        :param request (bytes):the serialized request
        :param result (FutureResult):
        """
        self._in_process_transactions_count.dec()
        req = processor_pb2.TpProcessRequest()
        req.ParseFromString(request)
        # If raw header bytes were sent then deserialize to get
        # transaction family name and version
        if req.header_bytes == b'':
            # When header_bytes field is empty, the header field will
            # be populated, so we can use that directly.
            request_header = req.header
        else:
            # Deserialize the header_bytes
            request_header = transaction_pb2.TransactionHeader()
            request_header.ParseFromString(req.header_bytes)
        response = processor_pb2.TpProcessResponse()
        response.ParseFromString(result.content)

        processor_type = ProcessorType(
            request_header.family_name,
            request_header.family_version)

        self._processor_manager[processor_type].get_processor(
            result.connection_id).dec_occupancy()
        self._processor_manager.notify()

        self._get_tp_process_response_counter(
            response.Status.Name(response.status)).inc()

        if result.connection_id in self._open_futures and \
                req.signature in self._open_futures[result.connection_id]:
            del self._open_futures[result.connection_id][req.signature]

        if response.status == processor_pb2.TpProcessResponse.OK:
            state_sets, state_deletes, events, data = \
                self._context_manager.get_execution_results(req.context_id)

            state_changes = [
                transaction_receipt_pb2.StateChange(
                    address=addr,
                    value=value,
                    type=transaction_receipt_pb2.StateChange.SET)
                for addr, value in state_sets.items()
            ] + [
                transaction_receipt_pb2.StateChange(
                    address=addr,
                    type=transaction_receipt_pb2.StateChange.DELETE)
                for addr in state_deletes
            ]

            self._scheduler.set_transaction_execution_result(
                txn_signature=req.signature,
                is_valid=True,
                context_id=req.context_id,
                state_changes=state_changes,
                events=events,
                data=data)

        elif response.status == processor_pb2.TpProcessResponse.INTERNAL_ERROR:
            LOGGER.error(
                "Transaction processor internal error: %s "
                "(transaction: %s, name: %s, version: %s)",
                response.message,
                req.signature,
                request_header.family_name,
                request_header.family_version)

            # Make sure that the transaction wasn't unscheduled in the interim
            if self._scheduler.is_transaction_in_schedule(req.signature):
                self._execute(
                    processor_type=processor_type,
                    process_request=req)

        else:
            self._context_manager.delete_contexts(
                context_id_list=[req.context_id])

            self._fail_transaction(
                txn_signature=req.signature,
                context_id=req.context_id,
                error_message=response.message,
                error_data=response.extended_data)

    def execute_thread(self):
        try:
            self._execute_schedule()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception(
                "Unhandled exception while executing schedule: %s", exc)

    def _execute_schedule(self):
        for txn_info in self._scheduler:
            self._transaction_execution_count.inc()

            txn = txn_info.txn
            header = transaction_pb2.TransactionHeader()
            header.ParseFromString(txn.header)

            processor_type = ProcessorType(
                header.family_name,
                header.family_version)

            config = self._settings_view_factory.create_settings_view(
                txn_info.state_hash)

            transaction_families = config.get_setting(
                key=self._tp_settings_key,
                default_value="[]")

            # After reading the transaction families required in configuration
            # try to json.loads them into a python object
            # If there is a misconfiguration, proceed as if there is no
            # configuration.
            try:
                transaction_families = json.loads(transaction_families)
                required_transaction_processors = [
                    ProcessorType(
                        d.get('family'),
                        d.get('version')) for d in transaction_families]
            except ValueError:
                LOGGER.error("sawtooth.validator.transaction_families "
                             "misconfigured. Expecting a json array, found"
                             " %s", transaction_families)
                required_transaction_processors = []

            # First check if the transaction should be failed
            # based on configuration
            if required_transaction_processors and \
                    processor_type not in required_transaction_processors:
                # The txn processor type is not in the required
                # transaction processors so
                # failing transaction right away
                LOGGER.debug("failing transaction %s of type (name=%s,"
                             "version=%s) since it isn't"
                             " required in the configuration",
                             txn.header_signature,
                             processor_type.name,
                             processor_type.version)

                self._fail_transaction(txn.header_signature)
                continue

            if processor_type in required_transaction_processors:
                # The txn processor type is in the required
                # transaction processors: check all the outputs of
                # the transaction match one namespace listed
                transaction_family = \
                    next(t for t in transaction_families
                         if t.get('family') == header.family_name
                         and t.get('version') == header.family_version)

                # if no namespaces are indicated, then the empty prefix is
                # inserted by default
                namespaces = transaction_family.get('namespaces', [''])
                if not isinstance(namespaces, list):
                    LOGGER.error("namespaces should be a list for "
                                 "transaction family (name=%s, version=%s)",
                                 processor_type.name,
                                 processor_type.version)
                prefixes = header.outputs
                bad_prefixes = [
                    prefix for prefix in prefixes
                    if not any(prefix.startswith(n) for n in namespaces)
                ]
                for prefix in bad_prefixes:
                    # log each
                    LOGGER.debug("failing transaction %s of type (name=%s,"
                                 "version=%s) because of no namespace listed "
                                 "in %s from the configuration settings can "
                                 "match the prefix %s",
                                 txn.header_signature,
                                 processor_type.name,
                                 processor_type.version,
                                 namespaces,
                                 prefix)

                if bad_prefixes:
                    self._fail_transaction(txn.header_signature)
                    continue

            try:
                context_id = self._context_manager.create_context(
                    state_hash=txn_info.state_hash,
                    base_contexts=txn_info.base_context_ids,
                    inputs=list(header.inputs),
                    outputs=list(header.outputs))
            except KeyError:
                LOGGER.error(
                    "Error creating context for transaction %s, "
                    "scheduler provided a base context that was not "
                    "in the context manager.", txn.header_signature)
                self._scheduler.set_transaction_execution_result(
                    txn_signature=txn.header_signature,
                    is_valid=False,
                    context_id=None)
                continue
            except CreateContextException:
                LOGGER.exception("Exception creating context")
                self._scheduler.set_transaction_execution_result(
                    txn_signature=txn.header_signature,
                    is_valid=False,
                    context_id=None)
                continue

            process_request = processor_pb2.TpProcessRequest(
                header=header,
                payload=txn.payload,
                signature=txn.header_signature,
                context_id=context_id,
                header_bytes=txn.header)

            # Since we have already checked if the transaction should be failed
            # all other cases should either be executed or waited for.
            self._execute(
                processor_type=processor_type,
                process_request=process_request)

        self._done = True

    def _execute(self, processor_type, process_request):
        try:
            processor = self._processor_manager.get_next_of_type(
                processor_type=processor_type)
        except WaitCancelledException:
            LOGGER.exception("Transaction %s cancelled while "
                             "waiting for available processor",
                             process_request.signature)
            return

        # Previously, both header and header_bytes fields were filled into the
        # protobuf object, because the earlier code does not have the correct
        # context to determine which to fill in. The chosen transaction
        # processor has the context information.
        # So here, we make sure only the correct field contains data.
        if processor.request_header_style() == \
                processor_pb2.TpRegisterRequest.EXPANDED:
            # Send transaction header with empty header_bytes
            process_request.header_bytes = b''
        elif processor.request_header_style() == \
                processor_pb2.TpRegisterRequest.RAW:
            # Send empty transaction header with header_bytes
            process_request.header.CopyFrom(
                transaction_pb2.TransactionHeader())
        else:
            raise AssertionError(
                "TpRegisterRequest should request either expanded or raw "
                "header style. Currently there's none set.")
        self._send_and_process_result(
            process_request, processor.connection_id)

    def _fail_transaction(self, txn_signature,
                          context_id=None, error_message=None,
                          error_data=None):
        self._scheduler.set_transaction_execution_result(
            txn_signature=txn_signature,
            is_valid=False,
            context_id=context_id,
            error_message=error_message,
            error_data=error_data)

        for observer in self._invalid_observers:
            observer.notify_txn_invalid(
                txn_signature,
                error_message,
                error_data)

    def _send_and_process_result(self, process_request, connection_id):
        content = process_request.SerializeToString()
        fut = self._service.send(
            validator_pb2.Message.TP_PROCESS_REQUEST,
            content,
            connection_id=connection_id,
            callback=self._future_done_callback)
        self._in_process_transactions_count.inc()
        if connection_id in self._open_futures:
            self._open_futures[connection_id].update(
                {process_request.signature: fut})
        else:
            self._open_futures[connection_id] = \
                {process_request.signature: fut}

    def remove_broken_connection(self, connection_id):
        self._processor_manager.remove(connection_id)
        if connection_id not in self._open_futures:
            # Connection has already been removed.
            return
        futures_to_set = [
            self._open_futures[connection_id][key]
            for key in self._open_futures[connection_id]
        ]

        response = processor_pb2.TpProcessResponse(
            status=processor_pb2.TpProcessResponse.INTERNAL_ERROR)
        result = FutureResult(
            message_type=validator_pb2.Message.TP_PROCESS_RESPONSE,
            content=response.SerializeToString(),
            connection_id=connection_id)
        for fut in futures_to_set:
            fut.set_result(result)
            self._future_done_callback(fut.request, result)

    def is_done(self):
        return self._done

    def cancel(self):
        self._processor_manager.cancel()
        self._scheduler.cancel()


class TransactionExecutor:
    def __init__(self,
                 service,
                 context_manager,
                 settings_view_factory,
                 scheduler_type,
                 invalid_observers=None):
        """
        Args:
            service (Interconnect): The zmq internal interface
            context_manager (ContextManager): Cache of state for tps
            settings_view_factory (SettingsViewFactory): Read-only view of
                setting state.
        Attributes:
            processor_manager (ProcessorManager): All of the registered
                transaction processors and a way to find the next one to send
                to.
        """
        self._service = service
        self._context_manager = context_manager
        self.processor_manager = ProcessorManager(RoundRobinProcessorIterator)
        self._settings_view_factory = settings_view_factory
        self._executing_threadpool = \
            InstrumentedThreadPoolExecutor(max_workers=5, name='Executing')
        self._alive_threads = []
        self._lock = threading.Lock()

        self._invalid_observers = ([] if invalid_observers is None
                                   else invalid_observers)

        self._scheduler_type = scheduler_type

    def create_scheduler(self,
                         first_state_root,
                         always_persist=False):

        # Useful for a logical first state root of ""
        if not first_state_root:
            first_state_root = self._context_manager.get_first_root()

        if self._scheduler_type == "serial":
            scheduler = SerialScheduler(
                squash_handler=self._context_manager.get_squash_handler(),
                first_state_hash=first_state_root,
                always_persist=always_persist)
        elif self._scheduler_type == "parallel":
            scheduler = ParallelScheduler(
                squash_handler=self._context_manager.get_squash_handler(),
                first_state_hash=first_state_root,
                always_persist=always_persist)

        else:
            raise AssertionError(
                "Scheduler type must be either serial or parallel. Current"
                " scheduler type is {}.".format(self._scheduler_type))

        self.execute(scheduler=scheduler)
        return scheduler

    def check_connections(self):
        self._executing_threadpool.submit(self._check_connections)

    def _remove_done_threads(self):
        for t in self._alive_threads.copy():
            if t.is_done():
                with self._lock:
                    self._alive_threads.remove(t)

    def _cancel_threads(self):
        for t in self._alive_threads:
            if not t.is_done():
                t.cancel()

    def _check_connections(self):
        # This is not ideal, because it locks up the current thread while
        # waiting for the results.
        try:
            with self._lock:
                futures = {}
                for connection_id in \
                        self.processor_manager.get_all_processors():
                    fut = self._service.send(
                        validator_pb2.Message.PING_REQUEST,
                        network_pb2.PingRequest().SerializeToString(),
                        connection_id=connection_id)
                    futures[fut] = connection_id
                for fut in futures:
                    try:
                        fut.result(timeout=10)
                    except FutureTimeoutError:
                        LOGGER.warning(
                            "%s did not respond to the Ping, removing "
                            "transaction processor.", futures[fut])
                        self._remove_broken_connection(futures[fut])
        except Exception:  # pylint: disable=broad-except
            LOGGER.exception('Unhandled exception while checking connections')

    def _remove_broken_connection(self, connection_id):
        for t in self._alive_threads:
            t.remove_broken_connection(connection_id)

    def execute(self, scheduler):
        self._remove_done_threads()
        t = TransactionExecutorThread(
            service=self._service,
            context_manager=self._context_manager,
            scheduler=scheduler,
            processor_manager=self.processor_manager,
            settings_view_factory=self._settings_view_factory,
            invalid_observers=self._invalid_observers)
        self._executing_threadpool.submit(t.execute_thread)
        with self._lock:
            self._alive_threads.append(t)

    def stop(self):
        self._cancel_threads()
        self._executing_threadpool.shutdown(wait=True)


class InvalidTransactionObserver(metaclass=abc.ABCMeta):
    """An interface class for components wishing to be notified when a
    Transaction Processor finds a Transaction is invalid.
    """

    @abc.abstractmethod
    def notify_txn_invalid(self, txn_id, message=None, extended_data=None):
        """This method will be called when a Transaction Processor sends back
        a Transaction with the status INVALID_TRANSACTION, and includes any
        error message or extended data sent back.

        Args:
            txn_id (str): The id of the invalid Transaction
            message (str, optional): Message explaining why it is invalid
            extended_data (bytes, optional): Additional error data
        """
        raise NotImplementedError('InvalidTransactionObservers must have a '
                                  '"notify_txn_invalid" method')

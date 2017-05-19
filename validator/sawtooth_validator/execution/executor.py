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

from concurrent.futures import ThreadPoolExecutor
import json
import logging
import threading
import queue

from sawtooth_validator.protobuf import processor_pb2
from sawtooth_validator.protobuf import transaction_pb2
from sawtooth_validator.protobuf import validator_pb2

from sawtooth_validator.execution.scheduler_serial import SerialScheduler
from sawtooth_validator.execution.scheduler_parallel import ParallelScheduler
from sawtooth_validator.execution import processor_iterator


LOGGER = logging.getLogger(__name__)


class TransactionExecutorThread(object):
    """A thread of execution controlled by the TransactionExecutor.
    Provides the functionality that the journal can process on several
    schedulers at once.
    """
    def __init__(self,
                 service,
                 context_manager,
                 scheduler,
                 processors,
                 waiting_threadpool,
                 config_view_factory):
        """

        Args:
            service (Interconnect): The zmq internal interface
            context_manager (ContextManager): The cached state for tps
            scheduler (scheduler.Scheduler): Provides the order of txns to
                execute.
            processors (ProcessorIteratorCollection): Provides the next
                transaction processor to send to.
            waiters_by_type (_WaitersByType): Queues up transactions based on
                processor type.
            waiting_threadpool (ThreadPoolExecutor): A thread pool to run
                indefinite waiting functions in.
            config_view_factory (ConfigViewFactory): Read the configuration
                state
        Attributes:
            _tp_config_key (str): the key used to reference the part of state
                where the list of required transaction processors are.
        """
        super(TransactionExecutorThread, self).__init__()
        self._service = service
        self._context_manager = context_manager
        self._scheduler = scheduler
        self._processors = processors
        self._config_view_factory = config_view_factory
        self._tp_config_key = "sawtooth.validator.transaction_families"
        self._waiters_by_type = _WaitersByType()
        self._waiting_threadpool = waiting_threadpool
        self._done = False

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

    def execute_thread(self):
        for txn_info in self._scheduler:
            txn = txn_info.txn
            header = transaction_pb2.TransactionHeader()
            header.ParseFromString(txn.header)

            processor_type = processor_iterator.ProcessorType(
                header.family_name,
                header.family_version,
                header.payload_encoding)

            config = self._config_view_factory.create_config_view(
                txn_info.state_hash)
            transaction_families = config.get_setting(
                key=self._tp_config_key,
                default_value="[]")

            # After reading the transaction families required in configuration
            # try to json.loads them into a python object
            # If there is a misconfiguration, proceed as if there is no
            # configuration.
            try:
                transaction_families = json.loads(transaction_families)
                required_transaction_processors = [
                    processor_iterator.ProcessorType(
                        d.get('family'),
                        d.get('version'),
                        d.get('encoding')) for d in transaction_families]
            except ValueError:
                LOGGER.warning("sawtooth.validator.transaction_families "
                               "misconfigured. Expecting a json array, found"
                               " %s", transaction_families)
                required_transaction_processors = []

            # First check if the transaction should be failed
            # based on configuration
            if processor_type not in required_transaction_processors \
                    and len(required_transaction_processors) > 0:
                # The txn processor type is not in the required
                # transaction processors so
                # failing transaction right away
                LOGGER.debug("failing transaction %s of type (name=%s,"
                             "version=%s,encoding=%s) since it isn't"
                             " required in the configuration",
                             txn.header_signature,
                             processor_type.name,
                             processor_type.version,
                             processor_type.encoding)

                self._scheduler.set_transaction_execution_result(
                    txn_signature=txn.header_signature,
                    is_valid=False,
                    context_id=None)
                continue

            context_id = self._context_manager.create_context(
                state_hash=txn_info.state_hash,
                base_contexts=txn_info.base_context_ids,
                inputs=list(header.inputs),
                outputs=list(header.outputs))
            content = processor_pb2.TpProcessRequest(
                header=txn.header,
                payload=txn.payload,
                signature=txn.header_signature,
                context_id=context_id).SerializeToString()

            # Since we have already checked if the transaction should be failed
            # all other cases should either be executed or waited for.
            self._execute_or_wait_for_processor_type(
                processor_type=processor_type,
                content=content)

        self._done = True

    def _execute_or_wait_for_processor_type(self, processor_type, content):
        processor = self._processors.get_next_of_type(
            processor_type=processor_type)
        if processor is None:
            LOGGER.debug("no transaction processors registered for "
                         "processor type %s", processor_type)
            if processor_type not in self._waiters_by_type:
                in_queue = queue.Queue()
                in_queue.put_nowait(content)
                waiter = _Waiter(self._send_and_process_result,
                                 processor_type=processor_type,
                                 processors=self._processors,
                                 in_queue=in_queue,
                                 waiters_by_type=self._waiters_by_type)
                self._waiters_by_type[processor_type] = waiter
                self._waiting_threadpool.submit(waiter.run_in_threadpool)
            else:
                self._waiters_by_type[processor_type].add_to_in_queue(
                    content)
        else:
            connection_id = processor.connection_id
            self._send_and_process_result(content, connection_id)

    def _send_and_process_result(self, content, connection_id):
        self._service.send(validator_pb2.Message.TP_PROCESS_REQUEST,
                           content,
                           connection_id=connection_id,
                           callback=self._future_done_callback)

    def is_done(self):
        return self._done and len(self._waiters_by_type) == 0

    def cancel(self):
        for waiter in self._waiters_by_type.values():
            waiter.cancel()
        self._scheduler.cancel()


class TransactionExecutor(object):
    def __init__(self, service, context_manager, config_view_factory,
                 scheduler_type):
        """

        Args:
            service (Interconnect): The zmq internal interface
            context_manager (ContextManager): Cache of state for tps
            config_view_factory (ConfigViewFactory): Read-only view of config
                state.
        Attributes:
            processors (ProcessorIteratorCollection): All of the registered
                transaction processors and a way to find the next one to send
                to.
            _waiting_threadpool (ThreadPoolExecutor): A threadpool to run
                waiting to process transactions functions in.
            _waiters_by_type (_WaitersByType): Threadsafe map of ProcessorType
                to _Waiter that is waiting on a processor of that type.
        """
        self._service = service
        self._context_manager = context_manager
        self.processors = processor_iterator.ProcessorIteratorCollection(
            processor_iterator.RoundRobinProcessorIterator)
        self._config_view_factory = config_view_factory
        self._waiting_threadpool = ThreadPoolExecutor(max_workers=3)
        self._executing_threadpool = ThreadPoolExecutor(max_workers=5)
        self._alive_threads = []
        self._lock = threading.Lock()
        self._scheduler_type = scheduler_type

    def create_scheduler(self,
                         squash_handler,
                         first_state_root,
                         always_persist=False):
        if self._scheduler_type == "serial":
            return SerialScheduler(squash_handler=squash_handler,
                                   first_state_hash=first_state_root,
                                   always_persist=always_persist)
        elif self._scheduler_type == "parallel":
            return ParallelScheduler(squash_handler=squash_handler,
                                     first_state_hash=first_state_root)

        else:
            raise AssertionError(
                "Scheduler type must be either serial or parallel. Current"
                " scheduler type is {}.".format(self._scheduler_type))

    def _remove_done_threads(self):
        for t in self._alive_threads.copy():
            if t.is_done():
                with self._lock:
                    self._alive_threads.remove(t)

    def _cancel_threads(self):
        for t in self._alive_threads:
            if not t.is_done():
                t.cancel()

    def execute(self, scheduler):
        self._remove_done_threads()
        t = TransactionExecutorThread(
            service=self._service,
            context_manager=self._context_manager,
            scheduler=scheduler,
            processors=self.processors,
            waiting_threadpool=self._waiting_threadpool,
            config_view_factory=self._config_view_factory)
        self._executing_threadpool.submit(t.execute_thread)
        with self._lock:
            self._alive_threads.append(t)

    def stop(self):
        self._cancel_threads()
        self._waiting_threadpool.shutdown(wait=True)
        self._executing_threadpool.shutdown(wait=True)


class _Waiter(object):
    """The _Waiter class waits for a transaction processor
    of a particular processor type to register and then processes
    all of the transactions that have queued up while waiting for the
    transaction processor.
    """

    def __init__(self,
                 send_and_process_func,
                 processor_type,
                 processors,
                 in_queue,
                 waiters_by_type):
        super().__init__()
        self._processors = processors
        self._processor_type = processor_type
        self._in_queue = in_queue
        self._send_and_process = send_and_process_func
        self._waiters_by_type = waiters_by_type
        self._cancelled_event = threading.Event()

    def add_to_in_queue(self, content):
        self._in_queue.put_nowait(content)

    def run_in_threadpool(self):
        LOGGER.info('Waiting for transaction processor (%s, %s, %s)',
                    self._processor_type.name,
                    self._processor_type.version,
                    self._processor_type.encoding)
        # Wait for the processor type to be registered
        self._processors.cancellable_wait(
            processor_type=self._processor_type,
            cancelled_event=self._cancelled_event)

        if self._cancelled_event.is_set():
            LOGGER.info("waiting cancelled on %s", self._processor_type)
            # The processing of transactions for a particular ProcessorType
            # has been cancelled.
            return

        while not self._in_queue.empty():
            content = self._in_queue.get_nowait()
            connection_id = self._processors.get_next_of_type(
                self._processor_type).connection_id
            self._send_and_process(content, connection_id)

        del self._waiters_by_type[self._processor_type]

    def cancel(self):
        self._cancelled_event.set()
        self._processors.notify()


class _WaitersByType(object):
    """Simple threadsafe datastructure to be a Map of ProcessorType: _Waiter
    pairs. It needs to be threadsafe so it can be accessed from each of the
    _Waiter threads after processing all of the queued transactions.
    """
    def __init__(self):
        self._waiters = {}
        self._lock = threading.RLock()

    def __contains__(self, item):
        with self._lock:
            return item in self._waiters

    def __getitem__(self, item):
        with self._lock:
            return self._waiters[item]

    def __setitem__(self, key, value):
        with self._lock:
            self._waiters[key] = value

    def __delitem__(self, key):
        with self._lock:
            del self._waiters[key]

    def __len__(self):
        with self._lock:
            return len(self._waiters)

    def values(self):
        """
        Returns (list of _Waiter): All the _Waiter objects.
        """
        with self._lock:
            return list(self._waiters.values())

    def keys(self):
        """
        Returns (list of _ProcessorType): All the ProcessorTypes waited for
        """
        with self._lock:
            return list(self._waiters.keys())

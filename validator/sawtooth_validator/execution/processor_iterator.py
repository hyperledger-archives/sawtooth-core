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

from abc import ABCMeta
from abc import abstractmethod
import itertools
import logging
from threading import RLock
from threading import Condition


LOGGER = logging.getLogger(__name__)


class ProcessorIteratorCollection(object):
    """Contains all of the registered (added via __setitem__)
    transaction processors in a _processors (dict) where the keys
    are ProcessorTypes and the values are ProcessorIterators.
    """

    def __init__(self, processor_iterator_class):
        # bytes: list of ProcessorType
        self._identities = {}
        # ProcessorType: ProcessorIterator
        self._processors = {}
        self._proc_iter_class = processor_iterator_class
        self._condition = Condition()

    def __getitem__(self, item):
        """Get a particular ProcessorIterator

        Args:
            item (ProcessorType): The processor type key.
        """
        with self._condition:
            return self._processors[item]

    def __contains__(self, item):
        with self._condition:
            return item in self._processors

    def get_next_of_type(self, processor_type):
        """Get the next processor of a particular type

        Args:
            processor_type (ProcessorType): The processor type associated with
                a zmq identity.

        Returns:
            (Processor): Information about the transaction processor
        """
        with self._condition:
            if processor_type in self:
                return self[processor_type].next_processor()
            return None

    def get_all_processors(self):
        processors = []
        for processor in self._processors.values():
            processors += processor.processor_identities()
        return processors

    def __setitem__(self, key, value):
        """Either create a new ProcessorIterator, if none exists for a
        ProcessorType, or add the Processor to the ProcessorIterator.

        Args:
            key (ProcessorType): The type of transactions this transaction
                processor can handle.
            value (Processor): Information about the transaction processor.
        """
        with self._condition:
            if key not in self._processors:
                proc_iterator = self._proc_iter_class()
                proc_iterator.add_processor(value)
                self._processors[key] = proc_iterator
            else:
                self._processors[key].add_processor(value)
            if value.connection_id not in self._identities:
                self._identities[value.connection_id] = [key]
            else:
                self._identities[value.connection_id].append(key)
            self._condition.notify_all()

    def remove(self, processor_identity):
        """Removes all of the Processors for
        a particular transaction processor zeromq identity.

        Args:
            processor_identity (str): The zeromq identity of the transaction
                processor.
        """
        with self._condition:
            processor_types = self._identities.get(processor_identity)
            if processor_types is None:
                LOGGER.warning("transaction processor with identity %s tried "
                               "to unregister but was not registered",
                               processor_identity)
                return
            for processor_type in processor_types:
                if processor_type not in self._processors:
                    LOGGER.warning("processor type %s not a known processor "
                                   "type but is associated with identity %s",
                                   processor_type,
                                   processor_identity)
                    continue
                self._processors[processor_type].remove_processor(
                    processor_identity=processor_identity)
                if not self._processors[processor_type]:
                    del self._processors[processor_type]

    def __repr__(self):
        return ",".join([repr(k) for k in self._processors])

    def cancellable_wait(self, processor_type, cancelled_event):
        """Waits for a particular processor type to register or until
        is_cancelled is True. is_cancelled cannot be part of this class
        since we aren't cancelling all waiting for a processor_type,
        but just this particular wait.

        Args:
            processor_type (ProcessorType): The family, and version of
                the transaction processor.
            cancelled_event (threading.Event): is_set() will return True when
                the wait is cancelled.

        Returns:
            None
        """
        with self._condition:
            self._condition.wait_for(
                lambda: processor_type in self or cancelled_event.is_set()
            )

    def notify(self):
        """Must be called after setting the cancelled_event, when
        cancelling a wait.
        """
        with self._condition:
            self._condition.notify_all()


class Processor(object):
    def __init__(self, connection_id, namespaces):
        self.connection_id = connection_id
        self.namespaces = namespaces

    def __repr__(self):
        return "{}: {}".format(self.connection_id,
                               list(self.namespaces))

    def __eq__(self, other):
        return self.connection_id == other.connection_id


class ProcessorType(object):
    def __init__(self, name, version):
        self.name = name
        self.version = version

    def __repr__(self):
        return "{}: {}".format(self.name, self.version)

    def __hash__(self):
        return hash((self.name, self.version))

    def __eq__(self, other):
        return self.name == other.name and self.version == other.version


class ProcessorIterator(object, metaclass=ABCMeta):
    """Subclasses of this class implement the particular
    processor choosing scheme. e.g. RoundRobin, etc.
    Implementations should be threadsafe between __next__
    and add_processor.
    """

    @abstractmethod
    def __next__(self):
        """Return the next processor by whatever method the
        subclass implements. Should never raise StopIteration.
        """
        raise NotImplementedError()

    @abstractmethod
    def add_processor(self, processor):
        """Add the processor to the available processors
        that __next__ returns.

        :param processor (core.Processor): a class that encapsulates
            a single processor
        """
        raise NotImplementedError()

    @abstractmethod
    def remove_processor(self, processor_identity):
        """Remove the processor (tied to a specific identity)
        from the ProcessorIterator

        :param processor_identity (str): zeromq identity of the transaction
                                         processor
        """
        raise NotImplementedError()

    @abstractmethod
    def __len__(self):
        """
        The number of transaction processors for a given type
        :return (int): the number of processors for a given type
        """
        raise NotImplementedError()

    def next_processor(self):
        return next(self)


class RoundRobinProcessorIterator(ProcessorIterator):
    def __init__(self):
        self._inf_iterator = None
        self._processors = []
        self._lock = RLock()

    def __next__(self):
        with self._lock:
            return next(self._inf_iterator)

    def __repr__(self):
        with self._lock:
            return repr(self._processors)

    def processor_identities(self):
        with self._lock:
            return [p.connection_id for p in self._processors]

    def add_processor(self, processor):
        with self._lock:
            self._processors.append(processor)
            self._inf_iterator = itertools.cycle(self._processors)

    def remove_processor(self, processor_identity):
        with self._lock:
            idx = self.processor_identities().index(processor_identity)
            self._processors.pop(idx)
            self._inf_iterator = itertools.cycle(self._processors)

    def __len__(self):
        with self._lock:
            return len(self._processors)

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

from abc import ABCMeta
from abc import abstractmethod
import itertools
from threading import RLock


class ProcessorIteratorCollection(object):

    def __init__(self, processor_iterator_class):
        self._processors = {}
        self._proc_iter_class = processor_iterator_class

    def __getitem__(self, item):
        """Get a particular ProcessorIterator

        :param item (ProcessorType):
        :return: (Processor)
        """
        return self._processors[item].next_processor()

    def __contains__(self, item):
        return item in self._processors

    def __setitem__(self, key, value):
        """Set a ProcessorIterator to a ProcessorType,
        if the key is already set, add the processor
        to the iterator.
        :param key (ProcessorType):
        :param value (Processor):
        """
        if key not in self._processors:
            proc_iterator = self._proc_iter_class()
            proc_iterator.add_processor(value)
            self._processors[key] = proc_iterator
        else:
            self._processors[key].add_processor(value)

    def __repr__(self):
        return ",".join([repr(k) for k in self._processors.keys()])


class Processor(object):
    def __init__(self, identity, namespaces):
        self.identity = identity
        self.namespaces = namespaces

    def __repr__(self):
        return "{}: {}".format(self.identity,
                               self.namespaces)


class ProcessorType(object):
    def __init__(self, name, version, encoding):
        self.name = name
        self.version = version
        self.encoding = encoding

    def __repr__(self):
        return "{}: {}: {}".format(self.name,
                                   self.version,
                                   self.encoding)

    def __hash__(self):
        return hash((self.name, self.version, self.encoding))

    def __eq__(self, other):
        return self.name == other.name and self.version == other.version \
            and self.encoding == other.encoding


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

    def add_processor(self, processor):
        with self._lock:
            self._processors.append(processor)
            self._inf_iterator = itertools.cycle(self._processors)

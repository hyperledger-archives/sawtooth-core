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

import abc


class Observer(object, metaclass=abc.ABCMeta):
    """Abstract class which when extended must implement one method: notify
    """
    @abc.abstractmethod
    def notify(self, observed, data=None):
        """This is the method which will be called on an observed event.
        It is up to child implementations to define what sort behavior should
        be triggered.

        Args:
            observed (Observable): The object being observed
            data (optional): Any extra data that the observer may need

        Raises:
            NotImplementedError: Raised if notify is not implemented by child
        """
        raise NotImplementedError('{} must implement a notify method'.format(
            _get_class_name(self, 'Observers')))


class Observable(object):
    """Tracks set of observers, notifying them when notify_observers is called.
    """
    def __init__(self):
        self._observers = set()

    def add_observer(self, observer):
        """Adds a new observer to be notified. If already added, it is ignored.

        Args:
            observer (Observer): The new Observer

        Raises:
            TypeError: Attempted to add observer that does not extend Observer
        """
        if not isinstance(observer, Observer):
            raise TypeError('{} must extend the Observer class!'.format(
                _get_class_name(observer, 'Observers')))
        self._observers.add(observer)

    def remove_observer(self, observer):
        """Removes an observer so it will no longer be notified.

        Args:
            observer (Observer): The new Observer
        """
        self._observers.discard(observer)

    def clear_observers(self):
        """Removes all observers.
        """
        self._observers.clear()

    def notify_observers(self, data=None):
        """Notifies all observers, sending optional data if provided.

        Args:
            data (optional): Any extra data that the observer may need
        """
        for observer in self._observers.copy():
            observer.notify(self, data)


def _get_class_name(obj, default='Object'):
    try:
        return obj.__name__
    except AttributeError:
        try:
            return obj.__class__.__name__
        except AttributeError:
            return default

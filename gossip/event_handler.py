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

"""
This module defines the EventHandler class which allows for the
registration, removal, and invocation of event callbacks.
"""

import logging

logger = logging.getLogger(__name__)


class EventHandler(object):
    """Handles the registration, removal, and invocation of event callbacks.

    Attributes:
        EventName (str): The name of the event handler.
    """

    def __init__(self, evname):
        """Constructor for the EventHandler class.

        Args:
            evname (str): The name of the event handler.
        """
        self.EventName = evname
        self._handlers = []

    def __iadd__(self, handler):
        self._handlers.append(handler)
        return self

    def __isub__(self, handler):
        self._handlers.remove(handler)
        return self

    def __call__(self, *args, **keywargs):
        try:
            # This calls all of the handlers, but will only return true if they
            # ALL return true.
            result = True
            for handler in self._handlers:
                if not handler(*args, **keywargs) is True:
                    result = False
            return result
        except:
            logger.exception('event handler %s failed', self.EventName)

    def fire(self, *args, **keywargs):
        """Execute all of the registered callbacks.

        Args:
            args (list): An unpacked list of arguments to pass to the
                callback.
            keywargs (list): An unpacked dict of arguments to pass to the
                callback.

        Returns:
            bool: True if ALL of the handlers return True. Otherwise
                returns False.
        """
        return self.__call__(*args, **keywargs)

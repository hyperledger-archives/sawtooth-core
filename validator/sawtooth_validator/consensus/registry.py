# Copyright 2018 Cargill Incorporated
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

from collections import namedtuple
from threading import RLock


class EngineNotRegistered(Exception):
    """The engine is not registered."""


EngineInfo = namedtuple('EngineInfo', ['connection_id', 'name', 'version'])


class ConsensusRegistry:
    """A thread-safe construct that stores the connection_id, name, and version
    of all registered consensus engines, and tracks which engine is currently
    active."""

    def __init__(self):
        self._registry = []
        self._active = None
        self._lock = RLock()

    def __bool__(self):
        with self._lock:
            return self._active is not None

    def register_engine(self, connection_id, name, version):
        with self._lock:
            self._registry.append(EngineInfo(connection_id, name, version))

    def activate_engine(self, name, version):
        with self._lock:
            # If there is already an active engine, remove it
            if self._active is not None:
                self._active = None
            try:
                self._active = next(
                    e for e in self._registry
                    if e.name == name and e.version == version)
            except StopIteration:
                # If engine isn't registered, just leave _active as None
                pass

    def deactivate_current_engine(self):
        with self._lock:
            self._active = None

    def get_active_engine_info(self):
        with self._lock:
            return self._active

    def is_active_engine_id(self, connection_id):
        with self._lock:
            return (
                self._active is not None
                and connection_id == self._active.connection_id)

    def is_active_engine_name_version(self, name, version):
        with self._lock:
            return (
                self._active is not None
                and name == self._active.name
                and version == self._active.version)

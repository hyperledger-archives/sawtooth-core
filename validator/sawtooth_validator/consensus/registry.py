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


class EngineAlreadyActive(Exception):
    """The engine is already active."""


EngineInfo = namedtuple(
    'EngineInfo', ['connection_id', 'name', 'version', 'additional_protocols'])


class ConsensusRegistry:
    """A thread-safe construct that stores the connection_id, name, version,
    and any additional supported protocols of all registered consensus engines,
    and tracks which engine is currently active."""

    def __init__(self):
        self._registry = []
        self._active = None
        self._lock = RLock()

    def __bool__(self):
        return self.has_active_engine()

    def has_active_engine(self):
        with self._lock:
            return self._active is not None

    def register_engine(self, connection_id, name, version,
                        additional_protocols):
        with self._lock:
            engine_info = EngineInfo(
                connection_id, name, version, additional_protocols)

            # If this engine is already registered or if there is an existing
            # engine that this one replaces (supports all the same protocols),
            # remove the old connection.
            def is_same_engine(eng):
                return eng.name == name and eng.version == version

            def is_replaced(eng):
                return (
                    engine_handles_protocol(eng.name, eng.version, engine_info)
                    and all([True for (n, v) in eng.additional_protocols
                             if engine_handles_protocol(n, v, engine_info)]))

            self._registry = list(filter(
                lambda e: not is_same_engine(e) and not is_replaced(e),
                self._registry))

            # If this engine displaced the active engine, reset active engine
            if self._active not in self._registry:
                self._active = None

            self._registry.append(engine_info)

    def activate_engine(self, name, version):
        with self._lock:
            if self._active is not None:
                if engine_handles_protocol(name, version, self._active):
                    raise EngineAlreadyActive()
                else:
                    # A different engine is active; remove it
                    self._active = None
            try:
                self._active = next(
                    e for e in self._registry
                    if engine_handles_protocol(name, version, e))
            except StopIteration:
                raise EngineNotRegistered()

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


def engine_handles_protocol(name, version, engine):
    return ((name, version) == (engine.name, engine.version)
            or (name, version) in engine.additional_protocols)

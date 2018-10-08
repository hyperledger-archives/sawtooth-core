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


EngineInfo = namedtuple('EngineInfo', ['connection_id', 'name', 'version'])


class ConsensusRegistry:
    """A thread-safe construct that stores the connection_id, name, and version
    of the currently registered consensus engine."""

    def __init__(self):
        self._info = None
        self._lock = RLock()

    def __bool__(self):
        with self._lock:
            return self._info is not None

    def register_engine(self, connection_id, name, version):
        with self._lock:
            self._info = EngineInfo(connection_id, name, version)

    def unregister_engine(self):
        with self._lock:
            self._info = None

    def get_engine_info(self):
        with self._lock:
            return self._info

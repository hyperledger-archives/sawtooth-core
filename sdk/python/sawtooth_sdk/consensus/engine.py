# Copyright 2018 Intel Corporation
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
# -----------------------------------------------------------------------------

import abc
from collections import namedtuple


StartupState = namedtuple(
    'StartupInfo',
    ['chain_head', 'peers', 'local_peer_info'])


PeerMessage = namedtuple(
    'PeerMessage',
    ['header', 'header_bytes', 'header_signature', 'content'])


class Engine(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def start(self, updates, service, startup_state):
        '''Called after the engine is initialized, when a connection to the
        validator has been established. Notifications from the
        validator are sent along UPDATES. SERVICE is used to send
        requests to the validator.

        Args:
            updates (Queue)
            service (Service)
            startup (StartupInfo)
        '''

    @abc.abstractmethod
    def stop(self):
        '''Called before the engine is dropped in order to give the engine a
        chance to notify peers and clean up.'''

    @abc.abstractproperty
    def version(self):
        '''Get the version of this engine.

        Return:
            str
        '''

    @abc.abstractproperty
    def name(self):
        '''Get the name of the engine, typically the algorithm being
        implemented.

        Return:
            str
        '''

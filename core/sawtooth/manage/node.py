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


class NodeController(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def start(self, node_name, http_port, gossip_port, genesis=False):
        raise NotImplementedError

    @abstractmethod
    def stop(self, node_name):
        raise NotImplementedError

    @abstractmethod
    def get_node_names(self):
        raise NotImplementedError

    @abstractmethod
    def is_running(self, node_name):
        raise NotImplementedError


class NodeCommandGenerator(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def get_commands(self):
        raise NotImplementedError


class NodeCommand(object):
    __metaclass__ = ABCMeta

    def execute(self, controller):
        raise NotImplementedError


class StartCommand(NodeCommand):
    def __init__(self, node_name, http_port, gossip_port, genesis=False):
        super(StartCommand, self).__init__()

        self._node_name = node_name
        self._genesis = genesis
        self._http_port = http_port
        self._gossip_port = gossip_port

    def execute(self, controller):
        controller.start(
            node_name=self._node_name,
            http_port=self._http_port,
            gossip_port=self._gossip_port,
            genesis=self._genesis)


class StopCommand(NodeCommand):
    def __init__(self, node_name):
        super(StopCommand, self).__init__()
        self._node_name = node_name

    def execute(self, controller):
        controller.stop(self._node_name)

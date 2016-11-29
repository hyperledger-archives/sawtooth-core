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


class NodeArguments(object):
    '''
    Structure to house arguments exposed by our validator cli
    '''
    def __init__(self, node_name, http_port=None, gossip_port=None,
                 currency_home=None, config_files=None, genesis=False):
        '''
        Args:
            node_name (str):
            http_port (int):
            gossip_port (int):
            currency_home (str):
            config_files (list<str>):
            genesis (bool):
        '''
        self.node_name = node_name
        self.http_port = http_port
        self.gossip_port = gossip_port
        self.currency_home = currency_home
        self.config_files = [] if config_files is None else config_files
        self.genesis = genesis


class NodeController(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def create_genesis_block(self, node_args):
        '''
        Args:
            node_args (NodeArguments):
        '''
        raise NotImplementedError

    @abstractmethod
    def start(self, node_args):
        '''
        Args:
            node_args (NodeArguments):
        '''
        raise NotImplementedError

    @abstractmethod
    def stop(self, node_name):
        raise NotImplementedError

    @abstractmethod
    def kill(self, node_name):
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


class GenesisCommand(NodeCommand):
    def __init__(self, node_args):
        '''
        Args:
            node_args (NodeArguments):
        '''
        super(GenesisCommand, self).__init__()
        self._node_args = node_args

    def execute(self, controller):
        controller.create_genesis_block(self._node_args)


class StartCommand(NodeCommand):
    def __init__(self, node_args):
        '''
        Args:
            node_args (NodeArguments):
        '''
        super(StartCommand, self).__init__()
        self._node_args = node_args

    def execute(self, controller):
        controller.start(self._node_args)


class StopCommand(NodeCommand):
    def __init__(self, node_name):
        super(StopCommand, self).__init__()
        self._node_name = node_name

    def execute(self, controller):
        controller.stop(self._node_name)


class KillCommand(NodeCommand):
    def __init__(self, node_name):
        super(KillCommand, self).__init__()
        self._node_name = node_name

    def execute(self, controller):
        controller.kill(self._node_name)

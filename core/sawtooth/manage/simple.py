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


from sawtooth.manage.node import NodeCommandGenerator
from sawtooth.manage.node import StartCommand
from sawtooth.manage.node import StopCommand


class SimpleNodeCommandGenerator(NodeCommandGenerator):
    def __init__(self):
        self._commands = []

    def get_commands(self):
        retval = self._commands
        self._commands = []
        return retval

    def start(self, node_args):
        self._commands.append(StartCommand(node_args))

    def stop(self, node_name):
        self._commands.append(StopCommand(node_name))

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

from threading import Thread


class ValidatorNetworkManager(object):
    def __init__(self,
                 node_controller,
                 node_command_generator):
        self._node_controller = node_controller
        self._node_command_generator = node_command_generator

    def update(self):
        commands = self._node_command_generator.get_commands()

        # execute commands in parallel
        threads = []
        for command in commands:
            thread = Thread(
                target=command.execute,
                args=(self._node_controller,))
            thread.start()
            threads.append(thread)

        # block until all threads have completed or timed out
        wait_time = 10
        for thread in threads:
            thread.join(wait_time)

    def get_node_names(self):
        return self._node_controller.get_node_names()

    def is_running(self, node_name):
        return self._node_controller.is_running(node_name)

    def status(self, node_name):
        if self.is_running(node_name):
            return 'RUNNING'
        return 'UNKNOWN'

    def get_ip(self, node_name):
        return self._node_controller.get_ip(node_name)

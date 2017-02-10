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

import os
import signal
import subprocess
import time
import yaml

from sawtooth_manage.node import NodeController
from sawtooth_manage.utils import get_executable_script


class SubprocessNodeController(NodeController):
    def __init__(self, state_dir=None):
        if state_dir is None:
            state_dir = \
                os.path.join(os.path.expanduser("~"), '.sawtooth', 'cluster')

        if not os.path.exists(state_dir):
            os.makedirs(state_dir)
        self._state_dir = state_dir
        self._state_file_path = os.path.join(self._state_dir, 'state.yaml')

    def _load_state(self):
        return yaml.load(open(self._state_file_path))

    def _save_state(self, state):
        with open(self._state_file_path, 'w') as state_file:
            yaml.dump(state, state_file, default_flow_style=False)

    def start(self, node_args):
        state = self._load_state()

        node_name = node_args.node_name
        node_num = int(node_name[len('validator-'):])

        base_component_port = 40000
        port = str(base_component_port + node_num)
        url = '0.0.0.0:' + port

        base_gossip_port = 8800
        gossip_port_num = str(base_gossip_port + node_num)
        gossip_port = 'tcp://0.0.0.0:' + gossip_port_num

        state['Nodes'][node_name]['pid'] = []

        commands = ['validator'] + state['Processors']
        if node_args.genesis:
            commands = ['sawtooth'] + commands

        for cmd in commands:
            # get_executable_script returns (path, executable)
            _, executable = get_executable_script(cmd)

            # validator takes ports as separate args, but this might change
            if cmd == 'validator':
                component = '--component-endpoint', url
                network = '--network-endpoint', gossip_port
                flags = component + network
            elif cmd == 'sawtooth':
                flags = 'admin', 'genesis'
            else:
                flags = (url,)

            handle = subprocess.Popen((executable,) + flags)

            pid = handle.pid
            state['Nodes'][node_name]['pid'] += [pid]

        self._save_state(state)

        if node_args.genesis:
            time.sleep(5)

    def _send_signal_to_node(self, signal_type, node_name):
        state = self._load_state()
        for pid in state['Nodes'][node_name]['pid']:
            os.kill(pid, int(signal_type))

    def stop(self, node_name):
        self._send_signal_to_node(signal.SIGTERM, node_name)

    def kill(self, node_name):
        self._send_signal_to_node(signal.SIGKILL, node_name)

    def get_node_names(self):
        state = self._load_state()
        return state['Nodes'].keys()

    def is_running(self, node_name):
        status = self._load_state()['Nodes'][node_name]['Status']
        return True if status == 'Running' else False

    def create_genesis_block(self, node_args):
        pass

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

import logging
import os
import signal
import subprocess
import sys
import time

import psutil

from sawtooth.exceptions import ManagementError
from sawtooth.manage.utils import find_txnvalidator

from sawtooth.manage.node import NodeController

LOGGER = logging.getLogger(__name__)


class DaemonNodeController(NodeController):
    def __init__(self, state_dir=None):
        if state_dir is None:
            state_dir = \
                os.path.join(os.path.expanduser("~"), '.sawtooth', 'cluster')

        if not os.path.exists(state_dir):
            os.makedirs(state_dir)

        self._state_dir = state_dir

    def _construct_args(self, node_name, http_port, gossip_port, genesis):
        validator_path = find_txnvalidator()

        args = []

        # Fix for windows, where script are not executable
        if os.name == 'nt' and not validator_path.endswith('.exe'):
            args.append(sys.executable)

        args.append(validator_path)
        args.append('-vv')

        pid_file = os.path.join(self._state_dir, "{}.pid".format(node_name))

        args.extend(['--node', node_name])

        args.extend([
            '--listen', '127.0.0.1:{}/UDP gossip'.format(gossip_port),
            '--listen', '127.0.0.1:{}/TCP http'.format(http_port)])

        args.extend(['--pidfile', pid_file])

        if genesis:
            args.append('--genesis')

        args.append('--daemon')

        return args

    def _join_args(self, args):
        formatted_args = []
        for arg in args:
            if ' ' in arg:
                formatted_args.append("'" + arg + "'")
            else:
                formatted_args.append(arg)
        return ' '.join(formatted_args)

    def start(self, node_args):
        node_name = node_args.node_name
        http_port = node_args.http_port
        gossip_port = node_args.gossip_port
        genesis = node_args.genesis
        args = self._construct_args(node_name, http_port, gossip_port,
                                    genesis)
        LOGGER.debug('starting %s: %s', node_name, self._join_args(args))

        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)

        handle = subprocess.Popen(args, env=env)
        handle.communicate()

    def stop(self, node_name):
        pid = self._get_validator_pid(node_name)
        os.kill(pid, signal.SIGKILL)

    def _get_validator_pid(self, node_name):
        pid_file = os.path.join(self._state_dir, "{}.pid".format(node_name))

        max_attempts = 3
        attempts = 0
        while attempts < max_attempts:
            if os.path.exists(pid_file):
                with open(pid_file, 'r') as fd:
                    try:
                        return int(fd.readline())
                    except ValueError:
                        if attempts >= max_attempts:
                            raise ManagementError(
                                "invalid pid file: {}".format(pid_file))
            time.sleep(1)
            attempts = attempts + 1

        raise ManagementError(
            "no such file: {}".format(pid_file))

    def get_node_names(self):
        node_names = []
        for filename in os.listdir(self._state_dir):
            if filename.endswith('.pid'):
                node_names.append(filename[:-len('.pid')])
        return node_names

    def is_running(self, node_name):
        pid_file = os.path.join(self._state_dir, "{}.pid".format(node_name))

        if os.path.exists(pid_file):
            with open(pid_file, 'r') as fd:
                try:
                    pid = int(fd.readline())
                except ValueError:
                    raise ManagementError(
                        "invalid pid file: {}".format(pid_file))
                if psutil.pid_exists(pid):
                    return True

        return False

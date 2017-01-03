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
import json
import logging
import os
import subprocess
import sys
import signal
import time
import psutil

from sawtooth.manage.node import NodeController
from sawtooth.manage.utils import get_executable_script
from sawtooth.validator_config import get_validator_configuration
from sawtooth.exceptions import ManagementError
from sawtooth.cli.exceptions import CliException

LOGGER = logging.getLogger(__name__)


class DaemonNodeController(NodeController):
    def __init__(self, host_name='localhost', verbose=False, state_dir=None):
        self._host_name = host_name
        self._verbose = verbose
        self._base_config = get_validator_configuration([], {})
        # Additional configuration for the genesis validator
        self._genesis_cfg = {
            "InitialConnectivity": 0,
        }
        # Additional configuration for the non-genesis validators
        self._non_genesis_cfg = {
            "InitialConnectivity": 1,
        }

        if state_dir is None:
            state_dir = \
                os.path.join(os.path.expanduser("~"), '.sawtooth', 'cluster')

        if not os.path.exists(state_dir):
            os.makedirs(state_dir)

        self._state_dir = state_dir

    def _construct_start_command(self, node_args):
        host = self._host_name
        node_name = node_args.node_name
        http_port = node_args.http_port
        gossip_port = node_args.gossip_port
        pid_file = os.path.join(self._state_dir, "{}.pid".format(node_name))
        cmd = get_executable_script('txnvalidator')
        if self._verbose is True:
            cmd += ['-vv']
        cmd += ['--node', node_name]
        cmd += ['--listen', "{}:{}/TCP http".format(host, http_port)]
        cmd += ['--listen', "{}:{}/UDP gossip".format(host, gossip_port)]
        cmd += ['--daemon']
        cmd += ['--pidfile', pid_file]

        for x in node_args.config_files:
            cmd += ['--config', x]
        # Create and indicate special config file
        config_dir = self._base_config['ConfigDirectory']
        if node_args.currency_home is not None:
            config_dir = os.path.join(node_args.currency_home, 'etc')
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
        config_file = '{}_bootstrap.json'.format(node_name)
        cfg = self._non_genesis_cfg
        if node_args.genesis:
            cfg = self._genesis_cfg

        with open(os.path.join(config_dir, config_file), 'w') as f:
            f.write(json.dumps(cfg, indent=4))
        cmd += ['--config', config_file]
        return cmd

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

    def _build_env(self, node_args):
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)
        if node_args.currency_home is not None:
            env['CURRENCYHOME'] = node_args.currency_home

        return env

    def create_genesis_block(self, node_args):
        '''
        Creates a key, then uses this key to author a genesis block.  The node
        corresponding to node_args must be initially available on the network
        in order to serve this genesis block.
        Args:
            node_args (NodeArguments):
        '''
        if self.is_running(node_args.node_name) is False:
            # Create key for initial validator
            cmd = get_executable_script('sawtooth')
            cmd += ['keygen', node_args.node_name]
            # ...sawtooth keygen does not assume validator's CURRENCYHOME
            key_dir = self._base_config['KeyDirectory']
            if node_args.currency_home is not None:
                key_dir = os.path.join(node_args.currency_home, 'keys')
            cmd += ['--key-dir', key_dir]
            if self._verbose is False:
                cmd += ['--quiet']
            proc = subprocess.Popen(cmd, env=self._build_env(node_args))
            proc.wait()
            # Create genesis block
            cmd = get_executable_script('sawtooth')
            cmd += ['admin', 'poet0-genesis']
            if self._verbose is True:
                cmd += ['-vv']
            cmd += ['--node', node_args.node_name]
            for x in node_args.config_files:
                cmd += ['--config', x]
            proc = subprocess.Popen(cmd, env=self._build_env(node_args))
            proc.wait()

    def start(self, node_args):
        '''
        Start a node if it is not already running.
        Args:
            node_args (NodeArguments):
        '''
        node_name = node_args.node_name
        if self.is_running(node_name) is False:
            cmd = self._construct_start_command(node_args)
            # Execute check_call and check for successful execution
            try:
                output = subprocess.check_output(
                    cmd, env=self._build_env(node_args))
            except subprocess.CalledProcessError as e:
                raise CliException(str(e))

        for line in output.split('\n'):
            if len(line) < 1:
                continue
            LOGGER.debug("command output: %s", str(line))

    def stop(self, node_name):
        pid = self._get_validator_pid(node_name)
        os.kill(pid, signal.SIGKILL)

    def kill(self, node_name):
        self.stop(node_name)

    def get_node_names(self):
        node_names = []
        for filename in os.listdir(self._state_dir):
            if filename.endswith('.pid'):
                node_names.append(filename[:-len('.pid')])
        return [x for x in node_names if self.is_running(x)]

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

    def get_ip(self, node_name):

        hostname = self._host_name
        return hostname

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
import subprocess
import yaml

from sawtooth.cli.exceptions import CliException

from sawtooth.manage.node import NodeController

LOGGER = logging.getLogger(__name__)


class _StateEntry(object):
    def __init__(self, name, identifier, status, command):
        self.name = name
        self.identifier = identifier
        self.status = status
        self.command = command


class DockerNodeController(NodeController):

    def __init__(self, state_dir=None):
        if state_dir is None:
            state_dir = \
                os.path.join(os.path.expanduser("~"), '.sawtooth', 'cluster')

        if not os.path.exists(state_dir):
            os.makedirs(state_dir)

        self._state_dir = state_dir

    def _construct_start_args(self, node_name, http_port, gossip_port,
                              genesis):
        # Check for running the network sawtooth and get the subnet
        subnet_arg = ['docker', 'network', 'inspect', 'sawtooth']
        try:
            output = yaml.load(subprocess.check_output(subnet_arg))
            subnet = output[0]['IPAM']['Config'][0]['Subnet'][:-4]
        except subprocess.CalledProcessError as e:
            raise CliException(str(e))

        num = str(int(node_name[10:]) + 3)
        ip_addr = subnet + num
        local_project_dir = '/project'

        args = ['docker', 'run', '-t', '-d', '--network', 'sawtooth']

        args.extend(['--name', node_name])
        args.extend(['--label', 'sawtooth.cluster=default'])
        args.extend(['--ip', ip_addr])
        args.extend(['-p', str(http_port)])
        args.extend(['-p', '{}/udp'.format(gossip_port)])
        args.extend(['-e', 'CURRENCYHOME=/project/sawtooth-core/validator'])
        args.extend(['-v', '{}:/project'.format(local_project_dir)])
        args.append('sawtooth-build-ubuntu-trusty')

        args.append('/project/sawtooth-core/bin/txnvalidator')
        args.extend(['--node', node_name])
        if genesis:
            args.append('--genesis')
        args.append('-vv')
        args.extend(['--listen',
                     '{}:{}/UDP gossip'.format(ip_addr, gossip_port)])
        args.extend(['--listen',
                     '{}:{}/TCP http'.format(ip_addr, http_port)])
        args.extend(['--url', 'http://{}3:8800'.format(subnet)])
        return args

    def _join_args(self, args):
        formatted_args = []
        for arg in args:
            if ' ' in arg:
                formatted_args.append("'" + arg + "'")
            else:
                formatted_args.append(arg)
        return ' '.join(formatted_args)

    def start(self, node_name, http_port, gossip_port, genesis=False):
        args = self._construct_start_args(node_name, http_port, gossip_port,
                                          genesis)
        LOGGER.debug('starting %s: %s', node_name, self._join_args(args))
        try:
            output = subprocess.check_output(args)
        except subprocess.CalledProcessError as e:
            raise CliException(str(e))

        for line in output.split('\n'):
            if len(line) < 1:
                continue
            LOGGER.debug("command output: %s", str(line))

    def stop(self, node_name):
        args = ['docker', 'stop', node_name]
        LOGGER.debug('stopping %s: %s', node_name, ' '.join(args))

        try:
            output = subprocess.check_output(args)
        except subprocess.CalledProcessError as e:
            raise CliException(str(e))

        for line in output.split('\n'):
            if len(line) < 1:
                continue
            LOGGER.debug("command output: %s", str(line))

        args = ['docker', 'rm', node_name]
        LOGGER.debug('stopping %s: %s', node_name, ' '.join(args))

        try:
            output = subprocess.check_output(args)
        except subprocess.CalledProcessError as e:
            raise CliException(str(e))

        for line in output.split('\n'):
            if len(line) < 1:
                continue
            LOGGER.debug("command output: %s", str(line))

    def _get_state(self):
        args = [
            'docker',
            'ps',
            '-a',
            '--no-trunc',
            '--format',
            '{{.Names}},{{.ID}},{{.Status}},{{.Label "sawtooth.cluster"}},'
            '{{.Command}}',
            '--filter',
            'label=sawtooth.cluster']

        try:
            output = subprocess.check_output(args)
        except subprocess.CalledProcessError as e:
            raise CliException(str(e))

        entries = []
        for line in output.split('\n'):
            if len(line) < 1:
                continue
            parts = line.split(',')
            entries.append(_StateEntry(
                name=parts[0],
                identifier=parts[1],
                status=parts[2],
                command=parts[3]))

        return entries

    def get_node_names(self):
        node_names = []
        for entry in self._get_state():
            node_names.append(entry.name)
        return node_names

    def is_running(self, node_name):
        for entry in self._get_state():
            if node_name == entry.name:
                return entry.status.startswith("Up")
        return False

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
import ipaddr
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
    '''
    Note that, for the present time, only node 0 may serve as the initial
    validator.
    '''

    def __init__(self, state_dir=None):
        if state_dir is None:
            state_dir = \
                os.path.join(os.path.expanduser("~"), '.sawtooth', 'cluster')

        if not os.path.exists(state_dir):
            os.makedirs(state_dir)

        self._state_dir = state_dir

    def _construct_start_args(self, node_name, http_port, gossip_port,
                              genesis):
        # only create 'genesis' ledger if there is not existing network
        if len(self.get_node_names()) > 0:
            genesis = False
        # Check for running the network sawtooth and get the subnet
        subnet_arg = ['docker', 'network', 'inspect', 'sawtooth']
        try:
            output = yaml.load(subprocess.check_output(subnet_arg))
            subnet = unicode(output[0]['IPAM']['Config'][0]['Subnet'])
            subnet_list = list(ipaddr.IPv4Network(subnet))
        except subprocess.CalledProcessError as e:
            raise CliException(str(e))

        num = int(node_name[len('validator-'):]) + 3

        if num < len(subnet_list) - 1:
            ip_addr = str(subnet_list[num])
        else:
            raise CliException("Out of Usable IP Addresses")
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
        args.extend(['bash', '-c'])

        cmd = []
        bin_path = '/project/sawtooth-core/bin'
        if genesis:
            cmd.append('echo "{\\\"InitialConnectivity\\\": 0}"')
            cmd.append('> ${CURRENCYHOME}/data/%s.json;' % node_name)
            cmd.append('%s/sawtooth keygen %s; ' % (bin_path, node_name))
            cmd.append('%s/sawtooth admin' % bin_path)
            cmd.append('poet0-genesis -vv --node %s; exec' % node_name)
        cmd.append('%s/txnvalidator' % bin_path)
        cmd.extend(['--node', node_name])
        cmd.append('-vv')
        cmd.append("--listen '{}:{}/UDP gossip'".format(ip_addr, gossip_port))
        cmd.append("--listen '{}:{}/TCP http'".format(ip_addr, http_port))
        # Set Ledger Url
        cmd.append("--url 'http://{}:8800'".format(str(subnet_list[3])))
        if genesis:
            cmd.append('--config ${CURRENCYHOME}/data/validator-000.json')
        args.append(' '.join(cmd))
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

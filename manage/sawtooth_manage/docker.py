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
import tempfile
import threading
import yaml

from sawtooth_manage.node import NodeController
from sawtooth_manage.exceptions import ManagementError


LOGGER = logging.getLogger(__name__)
SAWTOOTH_CORE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.realpath(__file__)
)))


class _StateEntry(object):
    def __init__(self, name, identifier, status, command):
        self.name = name
        self.identifier = identifier
        self.status = status
        self.command = command


class DockerNodeController(NodeController):

    def __init__(self, state_dir=None):
        """
        :param state_dir (str): optionally path to state directory
        """
        if state_dir is None:
            state_dir = os.path.join(os.path.expanduser("~"),
                                     '.sawtooth', 'cluster')

        if not os.path.exists(state_dir):
            os.makedirs(state_dir)

        self._state_dir = state_dir

        self._prefix = 'sawtooth-cluster-0'

        self._lock = threading.Lock()

    def _start_bridge_network(self):
        try:
            network_args = ['docker', 'network', 'create', '-d',
                            'bridge', self._prefix]
            n_output = subprocess.check_output(network_args)
            for l in n_output.splitlines():
                LOGGER.info(l)
        except subprocess.CalledProcessError as e:
            raise ManagementError(str(e))

    def _is_bridge_network_started(self):
        try:
            network_ls_args = ['docker', 'network', 'ls', '--filter',
                               'NAME={}'.format(self._prefix), '-q']
            network_output = subprocess.check_output(
                network_ls_args).splitlines()
            return len(network_output) > 0
        except subprocess.CalledProcessError as e:
            raise ManagementError(str(e))

    def _load_state(self):
        state_file_path = os.path.join(self._state_dir, 'state.yaml')
        with open(state_file_path) as fd:
            state = yaml.safe_load(fd)
        return state

    def _construct_start_args(self, node_name, path):
        args = [
            'docker-compose',
            '-p', self._prefix.replace('-', '') + node_name,
            '-f', path,
            'up', '-d'
        ]

        return args

    def _join_args(self, args):
        formatted_args = []
        for arg in args:
            if ' ' in arg:
                formatted_args.append("'" + arg + "'")
            else:
                formatted_args.append(arg)
        return ' '.join(formatted_args)

    def _find_peers(self):
        peers = []
        args = ['docker', 'inspect', self._prefix, '--format',
                '{{range .Containers }}{{.IPv4Address}}{{end}}']
        try:
            output = subprocess.check_output(args)
            peers = output.split(b"/16")
        except subprocess.CalledProcessError as e:
            raise ManagementError(str(e))
        return ['tcp://' + str(p) + ':8800' for p in peers if len(p) > 4]

    def start(self, node_args):
        base_network_port = 8800
        base_component_port = 4004
        node_name = node_args.node_name
        http_port = node_args.http_port

        # The first time a node is started, it should start a bridge
        # network. Subsequent nodes should wait until the network
        # has successfully been started.
        with self._lock:
            if not self._is_bridge_network_started():
                self._start_bridge_network()

        compose_file = os.path.join(
            tempfile.mkdtemp(),
            'docker-compose.yaml')

        start_args = self._construct_start_args(node_name, compose_file)
        LOGGER.debug('starting %s: %s', node_name, self._join_args(start_args))
        peers = self._find_peers()

        if node_args.genesis:
            command = 'bash -c "sawtooth admin keygen && \
            sawtooth admin genesis && \
            validator {} -v --endpoint tcp://{}:8800"'
        else:
            command = 'bash -c "sawtooth admin keygen && \
            validator {} -v --endpoint tcp://{}:8800"'
        if peers:
            command = command.format('--peers ' + ",".join(peers), node_name)
        else:
            command = command.format('', node_name)

        compose_dict = {
            'version': '2',
            'services': {
                'validator': {
                    'image': 'sawtooth-validator',
                    'expose': ['4004', '8800'],
                    'networks': {self._prefix: {},
                                 'default': {'aliases': [node_name]}},
                    'volumes': ['%s:/project/sawtooth-core' % SAWTOOTH_CORE],
                    'container_name': self._prefix + '-' + node_name,
                    'command': command
                }
            },
            'networks': {self._prefix: {'external': True}}
        }

        state = self._load_state()

        # add the processors
        node_num = node_name[len('validator-'):]
        processors = state['Processors']
        for proc in processors:
            compose_dict['services'][proc] = {
                'image': 'sawtooth-{}'.format(proc),
                'expose': ['4004'],
                'links': ['validator'],
                'volumes': ['%s:/project/sawtooth-core' % SAWTOOTH_CORE],
                'container_name': '-'.join([self._prefix, proc, node_num]),
                'command': '{} tcp://{}:4004'.format(proc, node_name)
            }

        # start the rest_api for the first node only
        if node_num == '000':
            compose_dict['services']['rest_api'] = {
                'image': 'sawtooth-rest_api',
                'expose': ['4004', '8080'],
                'links': ['validator'],
                'volumes': ['%s:/project/sawtooth-core' % SAWTOOTH_CORE],
                'container_name': '-'.join([self._prefix, 'rest_api',
                                            node_num]),
                'command': 'rest_api --connect tcp://{}:4004'.
                format(node_name),
                'ports': ['8080:8080']
            }

        # add the host:container port mapping for validator
        port_adder = http_port - base_network_port
        compose_dict['services']['validator']['ports'] = \
            [str(base_component_port + port_adder) + ":" + str(4004)]

        yaml.dump(compose_dict,
                  open(compose_file, mode='w'))

        try:
            output = subprocess.check_output(start_args)
        except subprocess.CalledProcessError:
            raise ManagementError(
                'Possibly unbuilt processors: {}'.format(processors))
        except OSError as e:
            if e.errno == 2:
                raise ManagementError("{}".format(str(e)))
            else:
                raise e

        for line in output.decode().split('\n'):
            if len(line) < 1:
                continue
            LOGGER.debug("command output: %s", str(line))

    def stop(self, node_name):
        state = self._load_state()

        node_num = node_name[len('validator-'):]

        # only first node has a rest_api process associated with it
        if node_num == '000':
            processes = state['Processors'] + ['rest_api'] + ['validator']
        else:
            processes = state['Processors'] + ['validator']

        containers = ['-'.join([self._prefix, proc, node_num])
                      for proc in processes]

        for c_name in containers:
            args = ['docker', 'stop', c_name]
            LOGGER.debug('stopping %s: %s', c_name, ' '.join(args))

            try:
                output = subprocess.check_output(args)
            except subprocess.CalledProcessError as e:
                raise ManagementError(str(e))

            for line in output.decode().split('\n'):
                if len(line) < 1:
                    continue
                LOGGER.debug("command output: %s", str(line))

            args = ['docker', 'rm', c_name]
            LOGGER.debug('stopping %s: %s', c_name, ' '.join(args))

            try:
                output = subprocess.check_output(args)
            except subprocess.CalledProcessError as e:
                raise ManagementError(str(e))

            for line in output.decode().split('\n'):
                if len(line) < 1:
                    continue
                LOGGER.debug("command output: %s", str(line))
            if 'validator' in c_name:
                network = c_name.replace('-', '') + '_default'
                args = ['docker', 'network', 'rm', network]
                try:
                    output = subprocess.check_output(args)
                except subprocess.CalledProcessError as e:
                    raise ManagementError(str(e))

                for line in output.splitlines():
                    if len(line) < 1:
                        continue
                    LOGGER.debug("command output: %s", str(line))

    def create_genesis_block(self, node_args):
        pass

    def kill(self, node_name):
        self.stop(node_name)

    def _get_state(self):
        args = [
            'docker',
            'ps',
            '--no-trunc',
            '--format',
            '{{.Names}},{{.ID}},{{.Status}},'
            '{{.Command}}',
            '--filter',
            'network={}'.format(self._prefix)]

        try:
            output = subprocess.check_output(args)
        except subprocess.CalledProcessError as e:
            raise ManagementError(str(e))
        except OSError as e:
            if e.errno == 2:
                raise ManagementError("{}:{}".format(str(e),
                                                     args[0]))

        entries = []
        for line in output.decode().split('\n'):
            if len(line) < 1:
                continue
            parts = line.split(',')
            entries.append(_StateEntry(
                name=parts[0].replace(self._prefix + '-', ''),
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

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


class DockerTNGNodeController(NodeController):

    def __init__(self, state_dir=None):
        """
        :param state_dir (str): optionally path to state directory
        """
        if state_dir is None:
            state_dir = \
                os.path.join(os.path.expanduser("~"), '.sawtooth', 'cluster')

        if not os.path.exists(state_dir):
            os.makedirs(state_dir)

        self._state_dir = state_dir

    def _construct_start_args(self, node_name):
        try:
            network_ls_args = ['docker', 'network', 'ls', '--filter',
                               'NAME=sawtooth-tng-cluster0', '-q']
            network_output = subprocess.check_output(
                network_ls_args).splitlines()
        except subprocess.CalledProcessError as e:
            raise CliException(str(e))

        if len(network_output) == 0:
            try:
                network_args = ['docker', 'network', 'create', '-d',
                                'bridge', 'sawtooth-tng-cluster0']
                n_output = subprocess.check_output(network_args)
                for l in n_output.splitlines():
                    LOGGER.info(l)
            except subprocess.CalledProcessError as e:
                raise CliException(str(e))
        args = ['docker-compose', '-p', 'sawtoothtngcluster0' + node_name,
                'up', '-d']

        return args

    def _join_args(self, args):
        formatted_args = []
        for arg in args:
            if ' ' in arg:
                formatted_args.append("'" + arg + "'")
            else:
                formatted_args.append(arg)
        return ' '.join(formatted_args)

    def start(self, node_config):
        node_name = node_config.node_name
        http_port = node_config.http_port
        args = self._construct_start_args(node_name)
        LOGGER.debug('starting %s: %s', node_name, self._join_args(args))
        compose_dir = tempfile.mkdtemp()
        compose_dict = {
            'version': '2',
            'services': {
                'validator': {
                    'image': 'sawtooth-validator',
                    'expose': ['40000'],
                    'networks': ['sawtooth-tng-cluster0', 'default'],
                    'volumes': ['/project:/project'],
                    'container_name': 'sawtooth-tng-cluster-0-' + node_name
                }
            },
            'networks': {'sawtooth-tng-cluster0': {'external': True}}
        }

        state_file_path = os.path.join(self._state_dir, 'state.yaml')
        state = yaml.load(file(state_file_path))
        # add the processors
        node_num = node_name[len('validator-'):]
        for proc in state['Processors']:
            service_name = proc[len('sawtooth-'):]

            compose_dict['services'][service_name] = {
                'image': proc,
                'expose': ['40000'],
                'links': ['validator'],
                'volumes': ['/project:/project'],
                'container_name': 'sawtooth-tng-cluster-0-'
                                  + service_name + node_num
            }

        # add the host:container port mapping for validator
        tng_http_port = http_port + 31200
        compose_dict['services']['validator']['ports'] = \
            [str(tng_http_port) + ":" + str(40000)]

        yaml.dump(compose_dict,
                  file(os.path.join(compose_dir, 'docker-compose.yaml'),
                       mode='w'))
        try:
            os.chdir(compose_dir)
            output = subprocess.check_output(args)
        except subprocess.CalledProcessError as e:
            raise CliException(str(e))

        for line in output.split('\n'):
            if len(line) < 1:
                continue
            LOGGER.debug("command output: %s", str(line))

    def stop(self, node_name):
        state_file_path = os.path.join(self._state_dir, 'state.yaml')
        state = yaml.load(file(state_file_path))
        node_num = node_name[len('validator-'):]
        processors = [p[len('sawtooth-'):] for p in state['Processors']]
        containers = ['sawtooth-tng-cluster-0-' + p + node_num
                      for p in processors]
        containers += ['sawtooth-tng-cluster-0-validator-' + node_num]
        for c_name in containers:
            args = ['docker', 'stop', c_name]
            LOGGER.debug('stopping %s: %s', c_name, ' '.join(args))

            try:
                output = subprocess.check_output(args)
            except subprocess.CalledProcessError as e:
                raise CliException(str(e))

            for line in output.split('\n'):
                if len(line) < 1:
                    continue
                LOGGER.debug("command output: %s", str(line))

            args = ['docker', 'rm', c_name]
            LOGGER.debug('stopping %s: %s', c_name, ' '.join(args))

            try:
                output = subprocess.check_output(args)
            except subprocess.CalledProcessError as e:
                raise CliException(str(e))

            for line in output.split('\n'):
                if len(line) < 1:
                    continue
                LOGGER.debug("command output: %s", str(line))
            if 'validator' in c_name:
                network = c_name.replace('-', '') + '_default'
                args = ['docker', 'network', 'rm', network]
                try:
                    output = subprocess.check_output(args)
                except subprocess.CalledProcessError as e:
                    raise CliException(str(e))

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
            '-a',
            '--no-trunc',
            '--format',
            '{{.Names}},{{.ID}},{{.Status}},'
            '{{.Command}}',
            '--filter',
            'network=sawtooth-tng-cluster0']

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
                name=parts[0].replace('sawtooth-tng-cluster-0-', ''),
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

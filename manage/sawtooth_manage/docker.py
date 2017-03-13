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
import threading

from sawtooth_manage.node import NodeController
from sawtooth_manage.exceptions import ManagementError


LOGGER = logging.getLogger(__name__)


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
            state = yaml.load(fd)
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

    def start(self, node_config):
        node_name = node_config.node_name
        http_port = node_config.http_port

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

        if node_config.genesis:
            entrypoint = 'bash -c "./bin/sawtooth admin keygen && \
            ./bin/sawtooth admin genesis && \
            ./bin/validator {} -v"'
        else:
            entrypoint = 'bash -c "./bin/sawtooth admin keygen && \
            ./bin/validator {} -v"'
        if len(peers) > 0:
            entrypoint = entrypoint.format('--peers ' + " ".join(peers))
        else:
            entrypoint = entrypoint.format('')

        compose_dict = {
            'version': '2',
            'services': {
                'validator': {
                    'image': 'sawtooth-validator',
                    'expose': ['40000', '8800'],
                    'networks': {self._prefix: {},
                                 'default': {'aliases': [node_name]}},
                    'volumes': ['/project:/project'],
                    'container_name': self._prefix + '-' + node_name,
                    'entrypoint': entrypoint
                }
            },
            'networks': {self._prefix: {'external': True}}
        }

        state = self._load_state()

        # add the processors
        node_num = node_name[len('validator-'):]
        for proc in state['Processors']:
            compose_dict['services'][proc] = {
                'image': 'sawtooth-{}'.format(proc),
                'expose': ['40000'],
                'links': ['validator'],
                'volumes': ['/project:/project'],
                'container_name': '-'.join([self._prefix, proc, node_num]),
                'entrypoint': 'bin/{} tcp://{}:40000'.format(proc, node_name)
            }

        # add the host:container port mapping for validator
        http_port = http_port + 31200
        compose_dict['services']['validator']['ports'] = \
            [str(http_port) + ":" + str(40000)]

        yaml.dump(compose_dict,
                  open(compose_file, mode='w'))

        try:
            output = subprocess.check_output(start_args)
        except subprocess.CalledProcessError as e:
            processors = state['Processors']
            # check if the docker image is built
            unbuilt = _get_unbuilt_images(processors)
            if unbuilt:
                raise ManagementError(
                    'Docker images not built: {}. Try running '
                    '"docker_build_all"'.format(
                        ', '.join(unbuilt)))

            invalid = _check_invalid_processors(processors)
            if invalid:
                raise ManagementError(
                    'No such processor: {}'.format(', '.join(invalid)))

            raise ManagementError(str(e))

        except OSError as e:
            if e.errno == 2:
                raise ManagementError("{}:{}".format(str(e), args[0]))
            else:
                raise e

        for line in output.decode().split('\n'):
            if len(line) < 1:
                continue
            LOGGER.debug("command output: %s", str(line))

    def stop(self, node_name):
        state = self._load_state()

        node_num = node_name[len('validator-'):]

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


# docker image checking -- these need to be kept up to date

def _get_unbuilt_images(processors):
    sawtooth_processors = [
        'sawtooth-' + processor
        for processor in processors + ['validator']
    ]
    built_ins = _built_in_processor_types()
    built_images = _get_built_images()

    unbuilt = [image for image in sawtooth_processors
               if image not in built_images and image in built_ins]

    return unbuilt

def _check_invalid_processors(processors):
    sawtooth_processors = [
        'sawtooth-' + processor
        for processor in processors + ['validator']
    ]
    built_ins = _built_in_processor_types()
    built_images = _get_built_images()

    invalid = [image for image in sawtooth_processors
               if image not in built_images and image not in built_ins]

    return invalid

def _get_built_images():
    docker_img_cmd = ['docker', 'images', '--format', '{{.Repository}}']
    return subprocess.check_output(docker_img_cmd).decode().split('\n')

def _built_in_processor_types():
    image_data_dir = os.path.join(
        os.path.dirname(__file__), '..', '..', 'docker')
    return os.listdir(image_data_dir)

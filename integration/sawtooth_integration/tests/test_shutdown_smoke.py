# Copyright 2017 Intel Corporation
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

# pylint: disable=broad-except

import unittest

import logging
import os
import socket
import subprocess
import time
import uuid

LOGGER = logging.getLogger(__name__)


class TestShutdownSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._sawtooth_core = cls._find_host_sawtooth_core()
        cls._id = os.environ.get("ISOLATION_ID", "latest")
        cls._validator_image = "{}:{}".format(
            os.environ.get("VALIDATOR_IMAGE_NAME"),
            cls._id)

    @unittest.skip("Skipping until STL-120 is complete: has periodic failures")
    def test_resting_shutdown_sigint(self):
        """Tests that SIGINT will cause validators with and without
        genesis to gracefully exit.

        Notes:
            1) A genesis validator and a non-genesis validator are started with
            the non-genesis validator specifying the genesis validator as
            a peer.
            2) The SIGINT os signal is sent to both validators.
            3) The validators' return codes are checked and asserted to be 0.
            4) Repeat step 1.
            5) The SIGTERM os signal is sent to both validators.
            6) The validators' return codes are checked and asserted to be 0.
        """

        # 1)
        containers = self._startup()

        try:
            # 2)
            for c in containers:
                self._send_docker_signal('SIGINT', c)
            initial_time = time.time()
            # 3)
            sigint_exit_statuses = self._wait_for_containers_exit_status(
                containers)

            end_time = time.time() - initial_time
            LOGGER.warning("Containers exited with sigint in %s seconds",
                           end_time)

            self.assertEqual(len(sigint_exit_statuses), len(containers))
            for s in sigint_exit_statuses:
                self.assertEqual(s, 0)

            self._log_and_clean_up(containers)
        except Exception as e:
            self._log_and_clean_up(containers)
            self.fail(str(e))

    @unittest.skip("Skipping until STL-120 is complete: has periodic failures")
    def test_resting_shutdown_sigterm(self):
        """Tests that SIGTERM will cause validators with and without
        genesis to gracefully exit.

        Notes:
            1) A genesis validator and a non-genesis validator are started with
            the non-genesis validator specifying the genesis validator as
            a peer.
            2) The SIGTERM os signal is sent to both validators.
            3) The validators' return codes are checked and asserted to be 0.
        """

        # 1)
        containers = self._startup()

        try:
            # 2)
            for c in containers:
                self._send_docker_signal('SIGTERM', c)
            initial_time = time.time()

            # 3)
            sigterm_exit_statuses = self._wait_for_containers_exit_status(
                containers)
            end_time = time.time() - initial_time
            LOGGER.warning("Containers exited with sigterm in %s seconds",
                           end_time)
            self.assertEqual(len(sigterm_exit_statuses), len(containers))
            for s in sigterm_exit_statuses:
                self.assertEqual(s, 0)

            self._log_and_clean_up(containers)
        except Exception as e:
            self._log_and_clean_up(containers)
            self.fail(str(e))

    def _send_docker_signal(self, sig, container_name):
        """
        Args:
            sig (str): examples: SIGTERM, SIGINT
            container_name (str): The name of the docker container
        """
        args = ['docker', 'kill', '--signal={}'.format(sig), container_name]

        # Not catching the CalledProcessError so the test errors and stops
        # if there is a problem calling docker.
        subprocess.run(
            args, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True)

    def _log_and_clean_up(self, containers):
        for container in containers:
            self._docker_logs(container)
        self._remove_docker_containers(containers)

    def _docker_logs(self, container):
        return subprocess.check_output(['docker', 'logs', container])

    def _wait_for_containers_exit_status(self, containers):
        """Wait for all of the specified containers to exit
        and return their exit codes.
        Args:
            containers (list of str): The containers to wait to exit.

        Returns:
            list of int: The list of return codes for the process in each
                container.

        """
        wait = ['docker', 'wait'] + containers
        handle = subprocess.Popen(
            args=wait,
            stdout=subprocess.PIPE,
            universal_newlines=True)
        try:
            output, _ = handle.communicate(timeout=35)
            return [int(e) for e in output.strip().split('\n')]
        except subprocess.TimeoutExpired:
            handle.kill()
            LOGGER.warning("Docker timed out waiting for %s to exit",
                           containers)
            return []

    def _start_container(self, container):
        start = ['docker', 'start', container]
        subprocess.run(start, timeout=15, check=True)

    def _docker_run(self, args):
        return subprocess.check_output(['docker', 'run'] + args,
                                       universal_newlines=True).strip('\n')

    def _run_genesis(self):
        return self._docker_run(
            ['-d',
             '-v',
             '{}:/project/sawtooth-core'.format(self._sawtooth_core),
             '-v',
             '/etc/sawtooth',
             '-v',
             '/var/lib/sawtooth',
             self._validator_image,
             'bash',
             '-c',
             "sawadm keygen && sawadm genesis"])

    def _start_validator(self, prior_container, early, extra):
        return self._docker_run(
            ['-d',
             '--volumes-from',
             prior_container,
             *early,
             self._validator_image,
             'validator',
             '-vv',
             *extra])

    def _remove_docker_containers(self, containers):
        return subprocess.check_call(['docker', 'rm', '-f'] + containers)

    def _run_keygen_non_genesis(self):
        return self._docker_run(
            ['-d',
             '-v',
             '{}:/project/sawtooth-core'.format(self._sawtooth_core),
             '-v',
             '/etc/sawtooth',
             self._validator_image,
             "bash",
             '-c',
             "sawadm keygen"])

    def _startup(self):
        containers = []
        try:
            genesis = self._run_genesis()
            self._wait_for_containers_exit_status([genesis])
            genesis_name = str(uuid.uuid4())
            validator_genesis = self._start_validator(
                genesis,
                ['--name', genesis_name],
                ['--endpoint', 'tcp://{}:8800'.format(genesis_name),
                 '--bind', 'component:tcp://eth0:4004',
                 '--bind', 'network:tcp://eth0:8800'])
            containers.append(validator_genesis)
            self._remove_docker_containers([genesis])
            keygen = self._run_keygen_non_genesis()
            self._wait_for_containers_exit_status([keygen])
            validator_1_name = str(uuid.uuid4())
            validator_non_genesis = self._start_validator(
                keygen, ['--link', validator_genesis,
                         '--name', validator_1_name],
                ['--peers', 'tcp://{}:8800'.format(genesis_name),
                 '--endpoint', 'tcp://{}:8800'.format(validator_1_name),
                 '--bind', 'component:tcp://eth0:4004',
                 '--bind', 'network:tcp://eth0:8800'])
            containers.append(validator_non_genesis)
            self._remove_docker_containers([keygen])
            # Make sure that the validators have completed startup -- cli path
            # and key loading, genesis check and creation
            time.sleep(3)
            return containers
        except Exception as e:
            self._remove_docker_containers(containers)
            self.fail(str(e))

    @classmethod
    def _find_host_sawtooth_core(cls):
        hostname = socket.gethostname()
        return subprocess.check_output(
            ['docker', 'inspect',
             '--format=\"{{ range .Mounts }}'
             '{{ if and (eq .Destination "/project/sawtooth-core") '
             '(eq .Type "bind") }}{{ .Source }}{{ end }}{{ end }}\"',
             hostname],
            universal_newlines=True).strip('\n').strip('\"')

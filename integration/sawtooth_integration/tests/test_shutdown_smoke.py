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

import unittest

import logging
import subprocess
import time

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


class TestShutdownSmoke(unittest.TestCase):
    def test_resting_shutdown(self):
        """Tests that SIGINT and SIGTERM will cause validators with and without
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
        # 2)
        containers = ['validator-genesis', 'validator-non-genesis']
        for c in containers:
            self._send_docker_signal('SIGINT', c)
        # 3)
        sigint_exit_statuses = self._wait_for_containers_exit_status(
            containers)

        self.assertEqual(len(sigint_exit_statuses), len(containers))
        for s in sigint_exit_statuses:
            self.assertEqual(s, 0)

        # 4)
        for c in containers:
            self._start_container(c)

        time.sleep(3)

        # 5)
        for c in containers:
            self._send_docker_signal('SIGTERM', c)

        # 6)
        sigterm_exit_statuses = self._wait_for_containers_exit_status(
            containers)
        self.assertEqual(len(sigterm_exit_statuses), len(containers))
        for s in sigterm_exit_statuses:
            self.assertEqual(s, 0)

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

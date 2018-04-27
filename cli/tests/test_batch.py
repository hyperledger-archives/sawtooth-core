# Copyright 2018 Intel Corporation
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

import argparse
import unittest
import logging
import subprocess
import shlex
import json
import csv
import yaml

from sawtooth_cli.rest_client import RestClient
from sawtooth_cli import batch

LOGGER = logging.getLogger(__name__)
REST_API = "localhost:8008"


class TestBatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._parser = None
        cls.REST_ENDPOINT = "http://" + REST_API

    def setUp(self):
        self._parser = argparse.ArgumentParser(add_help=False)
        self._rest_endpoint = self.REST_ENDPOINT \
            if self.REST_ENDPOINT.startswith("http://") \
            else "http://{}".format(self.REST_ENDPOINT)

        parent_parser = argparse.ArgumentParser(prog='test_batch',
                                                add_help=False)
        subparsers = self._parser.add_subparsers(title='subcommands',
                                                 dest='command')
        batch.add_batch_parser(subparsers, parent_parser)

    def _parse_batch_command(self, *args):
        cmd_args = ['batch']
        cmd_args += args
        return self._parser.parse_args(cmd_args)

    def test_batch_list(self):
        """Test for list of batches for specified formats
        """
        LOGGER.info('Testing with default format')
        response = _run_batch_command('sawtooth batch list --url {}'
                                      .format(self._rest_endpoint))
        data = response.split()
        keys = [data[0], data[1], data[2]]
        data_list = data[3:]
        data_list = [data_list[x:x + 3] for x in range(0, len(data_list), 3)]
        data = [{k: d for k, d in zip(keys, b)} for b in data_list]
        self.assertTrue(data, "Batch list not found")

        LOGGER.info('Testing with csv format')
        response = _run_batch_command(
            'sawtooth batch list --url {} --format {}'.format(
                self._rest_endpoint, 'csv'))
        reader = csv.DictReader(response.split('\n'), delimiter=',')
        data = [json.dumps(row) for row in reader]
        self.assertTrue(data, "Batch csv list not found")

        LOGGER.info('Testing with yaml format')
        response = _run_batch_command(
            'sawtooth batch list --url {} --format {}'.format(
                self._rest_endpoint, 'yaml'))
        data = yaml.load(response)
        self.assertTrue(data, "Batch yaml list not found")

        LOGGER.info('Testing with json format')
        response = _run_batch_command(
            'sawtooth batch list --url {} --format {}'.format(
                self._rest_endpoint, 'json'))
        data = json.loads(response)
        self.assertTrue(data, "Batch json list not found")

    def test_batch_show(self):
        """Test for batch show command for specified formats
        """
        args = self._parse_batch_command('list', '--url', self._rest_endpoint,
                                         '--format', 'json')
        keys = ('batch_id', 'txns', 'signer')

        def parse_batch_row(data):
            return (
                data['header_signature'],
                len(data.get('transactions', [])),
                data['header']['signer_public_key'])

        rest_client = RestClient(args.url, args.user)
        batches = rest_client.list_batches()
        data = [{k: d for k, d in zip(keys, parse_batch_row(b))}
                for b in batches]
        batch_id = data[0]['batch_id']

        LOGGER.info('Testing with yaml format')
        response = _run_batch_command(
            'sawtooth batch show {} --url {} --format {}'.format(
                batch_id, self._rest_endpoint, 'yaml'))
        self.assertTrue(response, "Batch yaml show not found")

        LOGGER.info('Testing with json format')
        response = _run_batch_command(
            'sawtooth batch show {} --url {} --format {}'.format(
                batch_id, self._rest_endpoint, 'json'))
        self.assertTrue(response, "Batch json show not found")

    def test_batch_status(self):
        """Test for batch status for specified formats
        """
        args = self._parse_batch_command('list', '--url', self._rest_endpoint,
                                         '--format', 'json')
        keys = ('batch_id', 'txns', 'signer')

        def parse_batch_row(data):
            return (
                data['header_signature'],
                len(data.get('transactions', [])),
                data['header']['signer_public_key'])

        rest_client = RestClient(args.url, args.user)
        batches = rest_client.list_batches()
        data = [{k: d for k, d in zip(keys, parse_batch_row(b))}
                for b in batches]
        batch_id = data[0]['batch_id']

        LOGGER.info('Testing with yaml format')
        response = _run_batch_command(
            'sawtooth batch status {} --url {} --format {}'.format(
                batch_id, self._rest_endpoint, 'yaml'))
        status = yaml.load(response)[0]['status']
        self.assertTrue(response, "Batch yaml status not found")
        self.assertTrue(status, "COMMITTED")

        LOGGER.info('Testing with json format')
        response = _run_batch_command(
            'sawtooth batch status {} --url {} --format {}'.format(
                batch_id, self._rest_endpoint, 'json'))
        status = json.loads(response)[0]['status']
        self.assertTrue(response, "Batch json status not found")
        self.assertTrue(status, "COMMITTED")


def _run_batch_command(command):
    return subprocess.check_output(
        shlex.split(command)
    ).decode().strip().replace("'", '"')

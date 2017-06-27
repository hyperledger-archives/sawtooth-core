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
import configparser
import getpass
import itertools
import logging
import os
import shutil
import time
import unittest
from unittest.mock import patch
from nose2.tools import params

from sawtooth_supplychain.common.exceptions import SupplyChainException

from sawtooth_supplychain.cli.main import main as cli

from sawtooth_supplychain.protobuf.agent_pb2 import Agent
from sawtooth_supplychain.protobuf.application_pb2 import Application
from sawtooth_supplychain.protobuf.record_pb2 import Record


LOGGER = logging.getLogger(__name__)


def _agent(identifier):
    return Agent(identifier='pk{}'.format(identifier),
                 name='name{}'.format(identifier))


def _agent_list(count):
    return [_agent(i) for i in range(count)]


def _application(identifier):
    return Application(record_identifier='identifier{}'.format(identifier),
                       applicant='pk{}'.format(identifier),
                       type=Application.OWNER)


def _application_list(count):
    return [_application(i) for i in range(count)]


def _record(identifier):

    return Record(identifier='identifier{}'.format(identifier),
                  creation_time=int(time.time()),
                  owners=[Record.AgentRecord(
                      agent_identifier='owner', start_time=1)],
                  custodians=[Record.AgentRecord(
                      agent_identifier='custodian', start_time=2)]
                  )


def _record_list(count):
    return [_record(i) for i in range(count)]


BAD_OPTIONS = [
    (('BAD',), SystemExit),
    (('--BAD',), SystemExit)]
BAD_REQUIRED_OPTIONS = [
    (None, SystemExit),
    (('--BAD',), SystemExit)]
RECORD_OPTIONS = [
    (None, SystemExit),
    (('record',), None)]
APPLICANT_OPTIONS = [
    (None, SystemExit),
    (('--applicant',), SystemExit),
    (('--applicant', "applicant"), None)]
TYPE_OPTIONS = [
    (None, SystemExit),
    (('--type',), SystemExit),
    (('--type', 'OWNER'), None)]


def _generate_cmd(args, options):
    out = []
    for option_list in options:
        cmd_line = args[:]
        exceptions = set()
        for opt in option_list:
            if opt[0] is not None:
                cmd_line.extend(opt[0])
            exceptions.add(opt[1])

        if None in exceptions:
            exceptions.remove(None)
        if len(exceptions) == 1:
            out.append((cmd_line, exceptions.pop()))
        elif len(exceptions) > 1:
            # there are multiple possible exceptions, verify that an
            # exception is raised. Nose2 does not provide checking for
            # one of a list of exceptions.
            out.append((cmd_line, Exception))
    return out


def _generate_cmd_combinations(args, *options):
    param_combinations = itertools.product(*options)
    out = _generate_cmd(args, param_combinations)
    return out


def _generate_bad_cmd_lines():
    return \
        _generate_cmd_combinations([], BAD_OPTIONS) + \
        _generate_cmd_combinations(['init'], BAD_OPTIONS) + \
        _generate_cmd_combinations(['init'],
                                   [(('--url',), SystemExit),
                                    (('--username',), SystemExit)]) + \
        _generate_cmd_combinations(['reset'], BAD_OPTIONS) + \
        _generate_cmd_combinations(['agent'], BAD_OPTIONS) + \
        _generate_cmd_combinations(['agent', 'show'],
                                   BAD_REQUIRED_OPTIONS) + \
        _generate_cmd_combinations(['agent', 'create'],
                                   BAD_REQUIRED_OPTIONS) + \
        _generate_cmd_combinations(['agent', 'list'],
                                   BAD_OPTIONS) + \
        _generate_cmd_combinations(['agent', 'show'],
                                   BAD_REQUIRED_OPTIONS) + \
        _generate_cmd_combinations(['application', 'create'],
                                   RECORD_OPTIONS,
                                   TYPE_OPTIONS) + \
        _generate_cmd_combinations(['application', 'list'],
                                   BAD_OPTIONS) + \
        _generate_cmd_combinations(['application', 'show'],
                                   RECORD_OPTIONS,
                                   APPLICANT_OPTIONS,
                                   TYPE_OPTIONS) + \
        _generate_cmd_combinations(['application', 'accept'],
                                   RECORD_OPTIONS,
                                   APPLICANT_OPTIONS,
                                   TYPE_OPTIONS) + \
        _generate_cmd_combinations(['application', 'reject'],
                                   RECORD_OPTIONS,
                                   APPLICANT_OPTIONS,
                                   TYPE_OPTIONS) + \
        _generate_cmd_combinations(['application', 'cancel'],
                                   RECORD_OPTIONS,
                                   TYPE_OPTIONS) + \
        _generate_cmd_combinations(['record', 'show'],
                                   BAD_REQUIRED_OPTIONS) + \
        _generate_cmd_combinations(['record', 'create'],
                                   BAD_REQUIRED_OPTIONS) + \
        _generate_cmd_combinations(['record', 'list'],
                                   BAD_OPTIONS) + \
        _generate_cmd_combinations(['record', 'show'],
                                   BAD_REQUIRED_OPTIONS)


class TestSupplyChainCli(unittest.TestCase):

    def setUp(self):
        # create a valid configuration for the tests
        cli('supplychain', ['init'])

    def cli(self, args):
        cli('supplychain', args)

    def clean_config(self):
        home = os.path.expanduser('~')
        config_dir = os.path.join(home, '.sawtooth')

        if os.path.exists(config_dir):
            shutil.rmtree(config_dir)
            LOGGER.info("Removing directory %s", config_dir)

    def config_filename(self):
        home = os.path.expanduser('~')
        return os.path.join(home, '.sawtooth', 'supplychain.cfg')

    def key_file_names(self, username=None):
        username = username or getpass.getuser()
        home = os.path.expanduser('~')
        priv_filename = os.path.join(
            home, '.sawtooth', 'keys', '{}.priv'.format(username))
        addr_filename = os.path.join(
            home, '.sawtooth', 'keys', '{}.addr'.format(username))

        return [priv_filename, addr_filename]

    def expect_files(self, files):
        for fle in files:
            if not os.path.exists(fle):
                self.fail('File {} does not exist.'.format(fle))

    def expect_no_files(self, files):
        for fle in files:
            if os.path.exists(fle):
                self.fail('File {} exists and should not.'.format(fle))

    def expect_config(self, config_filename, username, key_file, url):
        config = configparser.ConfigParser()
        config.read(config_filename)
        self.assertEqual(
            username, config.get('DEFAULT', 'username'))
        self.assertEqual(
            key_file, config.get('DEFAULT', 'key_file'))
        self.assertEqual(
            url, config.get('DEFAULT', 'url'))

    @params(*_generate_bad_cmd_lines())
    def test_argument_errors(self, args, error):
        ''' Verify the parsers handle bad argument conditions.
        '''
        with self.assertRaises(error):
            self.cli(args)

    @params(
        ('agent_create', ['agent', 'create', 'test']),
        ('agent_list', ['agent', 'list']),
        ('agent_get', ['agent', 'show', 'test']),
        ('application_create', ['application', 'create', 'test',
                                '--type', 'OWNER']),
        ('application_list', ['application', 'list']),
        ('application_get', ['application', 'show', 'test',
                             '--type', 'OWNER',
                             '--applicant', 'applicant']),
        ('application_accept', ['application', 'accept', 'test',
                                '--type', 'OWNER',
                                '--applicant', 'applicant']),
        ('application_reject', ['application', 'reject', 'test',
                                '--type', 'OWNER',
                                '--applicant', 'applicant']),
        ('application_cancel', ['application', 'cancel', 'test',
                                '--type', 'OWNER']),
        ('record_create', ['record', 'create', 'test']),
        ('record_list', ['record', 'list']),
        ('record_get', ['record', 'show', 'test']),
    )
    @patch("sawtooth_supplychain.cli.common.SupplyChainClient")
    # pylint: disable=invalid-name
    def test_client_error(self, patch_function, args, SupplyChainClient_mock):
        ''' Verify that client errors are passed back to the
        wrapper for reporting. These are valid command line options but
        we simulate an internal error in the client.
        '''

        fn = getattr(SupplyChainClient_mock.return_value, patch_function)
        fn.side_effect = SupplyChainException()
        with self.assertRaises(SupplyChainException):
            self.cli(args)

    def test_init_reset(self):
        '''
        Test the SupplyChain CLI implementation of environment initialization
        '''
        # Clean the environment
        username = getpass.getuser()
        url = '127.0.0.1:8080'
        config_filename = self.config_filename()
        key_files = self.key_file_names(username)
        config_files = [config_filename] + key_files
        self.clean_config()
        self.expect_no_files(config_files)

        # make sure a configuration is created
        self.cli(['init'])
        self.expect_files(config_files)
        self.expect_config(
            config_filename, username, key_files[0], url)

        # see that the configuration is cleaned up.
        self.cli(['reset'])
        self.expect_no_files(config_files)

    def test_init_reset_overides(self):
        '''
        Test the SupplyChain CLI implementation of environment initialization
        Verify the username and url overrides are honored.
        '''

        # verify the overrides
        username = getpass.getuser()
        url = '127.0.0.1:8080'
        config_filename = self.config_filename()
        key_files = self.key_file_names(username)
        config_files = [config_filename] + key_files

        self.cli(['init', '--username', username, '--url', url])
        self.expect_config(
            config_filename, username, key_files[0], url)

        # see that the configuration is cleaned up.
        self.cli(['reset'])
        self.expect_no_files(config_files)

    # the following parameters are:
    # 1) function to patch
    # 2) cli arguments
    # 3) return value from the patched function
    # 4) expected parameters to the patched function.
    # NOTE: the trailing commas in the single item tuples are intential. Python
    # requires this, () with out commas are treated as grouping operators not
    # as a tuple constructor.
    @params(
        ('agent_create', ['agent', 'create', 'test'],
         'OK', ('test',)),
        ('agent_list', ['agent', 'list'],
         _agent_list(2), ()),
        ('agent_list', ['agent', 'list'],
         _agent_list(0), ()),
        ('agent_list', ['agent', 'list'],
         None, ()),
        ('agent_get', ['agent', 'show', 'identifier'],
         _agent(1), ('identifier',)),
        ('agent_get', ['agent', 'show', 'identifier'],
            None, ('identifier',)),
        ('application_create', ['application', 'create', 'record',
                                '--type', 'OWNER'],
         'OK', ('record', Application.OWNER)),
        ('application_create', ['application', 'create', 'record',
                                '--type', 'CUSTODIAN'],
         'OK', ('record', Application.CUSTODIAN)),
        ('application_list', ['application', 'list'],
         _application_list(2), ()),
        ('application_list', ['application', 'list'],
         _application_list(0), ()),
        ('application_get', ['application', 'show', 'record',
                             '--type', 'OWNER',
                             '--applicant', 'applicant'],
         _application(1), ('record', 'applicant', Application.OWNER)),
        ('application_get', ['application', 'show', 'record',
                             '--type', 'CUSTODIAN',
                             '--applicant', 'applicant'],
         _application(1), ('record', 'applicant', Application.CUSTODIAN)),
        ('application_get', ['application', 'show', 'record',
                             '--type', 'OWNER',
                             '--applicant', 'applicant'],
         None, ('record', 'applicant', Application.OWNER)),
        ('application_accept', ['application', 'accept', 'record',
                                '--type', 'OWNER',
                                '--applicant', 'applicant'],
         'OK', ('record', 'applicant', Application.OWNER)),
        ('application_accept', ['application', 'accept', 'record',
                                '--type', 'CUSTODIAN',
                                '--applicant', 'applicant'],
         'OK', ('record', 'applicant', Application.CUSTODIAN)),
        ('application_reject', ['application', 'reject', 'record',
                                '--type', 'OWNER',
                                '--applicant', 'applicant'],
         'OK', ('record', 'applicant', Application.OWNER)),
        ('application_reject', ['application', 'reject', 'record',
                                '--type', 'CUSTODIAN',
                                '--applicant', 'applicant'],
         'OK', ('record', 'applicant', Application.CUSTODIAN)),
        ('application_cancel', ['application', 'cancel', 'record',
                                '--type', 'OWNER'],
         'OK', ('record', Application.OWNER)),
        ('application_cancel', ['application', 'cancel', 'record',
                                '--type', 'CUSTODIAN'],
         'OK', ('record', Application.CUSTODIAN)),
        ('record_create', ['record', 'create', 'test'],
         'OK', ('test',)),
        ('record_list', ['record', 'list'],
         _record_list(2), ()),
        ('record_list', ['record', 'list'],
         _record_list(0), ()),
        ('record_list', ['record', 'list'],
         None, ()),
        ('record_get', ['record', 'show', 'test'],
         _record(1), ('test',)),
        ('record_get', ['record', 'show', 'test'],
         None, ('test',))
    )
    @patch("sawtooth_supplychain.cli.common.SupplyChainClient")
    # pylint: disable=invalid-name
    def test_verify_valid_results(self, patch_function, args,
                                  result, expected_params,
                                  SupplyChainClient_mock):
        '''Test all valid command line options are properly parsed and
        the possible results from the client are correctly handled.
        '''
        fn = getattr(SupplyChainClient_mock.return_value, patch_function)
        fn.return_value = result
        self.cli(args)
        fn.assert_called_with(*expected_params)

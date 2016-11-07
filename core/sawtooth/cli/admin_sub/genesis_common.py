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

from journal.journal_core import Journal
from sawtooth.cli.exceptions import CliException
from sawtooth.config import ArgparseOptionsConfig
from sawtooth.validator_config import get_validator_configuration

LOGGER = logging.getLogger(__name__)


def genesis_info_file_name(directory):
    return os.path.join(directory, 'genesis_data.json')


def add_genesis_parser(subparsers, parent_parser, subparser_prefix):
    parser = subparsers.add_parser('%s-genesis' % subparser_prefix)
    parser.add_argument('--config',
                        help='Comma-separated list of config files to '
                             'load. Alternatively, multiple --config '
                             'options can be specified.',
                        action='append')
    parser.add_argument('--keyfile', help='Name of the key file')
    parser.add_argument('--conf-dir', help='Name of the config directory')
    parser.add_argument('--data-dir', help='Name of the data directory')
    parser.add_argument('--log-config', help='The python logging config file')
    parser.add_argument('--node', help='Short form name of the node')
    parser.add_argument('--type', help='Type of ledger to create')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='Increase output sent to stderr')
    parser.add_argument('-F', '--family',
                        help='Specify transaction families to load. Multiple'
                             ' -F options can be specified.',
                        action='append')


def mirror_validator_parsing(args):
    # Get ledger config:
    # ...set the default value of config because argparse 'default' in
    # ...combination with action='append' does the wrong thing.
    if args.config is None:
        args.config = ['txnvalidator.js']
    # ...convert any comma-delimited argument strings to list elements
    for arglist in [args.config]:
        if arglist is not None:
            for arg in arglist:
                if ',' in arg:
                    loc = arglist.index(arg)
                    arglist.pop(loc)
                    for element in reversed(arg.split(',')):
                        arglist.insert(loc, element)
    options_config = ArgparseOptionsConfig(
        [
            ('conf_dir', 'ConfigDirectory'),
            ('data_dir', 'DataDirectory'),
            ('type', 'LedgerType'),
            ('log_config', 'LogConfigFile'),
            ('keyfile', 'KeyFile'),
            ('node', 'NodeName'),
            ('verbose', 'Verbose'),
            ('family', 'TransactionFamilies')
        ], args)
    cfg = get_validator_configuration(args.config, options_config)
    # Duplicate some configuration massaging done by validator_cli
    from txnintegration.utils import read_key_file  # avoids dependency issue
    if "KeyFile" in cfg:
        keyfile = cfg["KeyFile"]
        if os.path.isfile(keyfile):
            LOGGER.info('read signing key from %s', keyfile)
            key = read_key_file(keyfile)
            cfg['SigningKey'] = key
        else:
            LOGGER.warn('unable to locate key file %s', keyfile)
    else:
        LOGGER.warn('no key file specified')
    return cfg


def check_for_chain(data_dir, node_name, store_type):
    block_store = Journal.get_store_file(node_name, 'block', data_dir,
                                         store_type=store_type)
    if os.path.isfile(block_store):
        msg = 'block store: %s exists; ' % block_store
        msg += 'skipping genesis block creation.'
        raise CliException(msg)

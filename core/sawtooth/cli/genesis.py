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
import socket

from gossip import node
from gossip.signed_object import generate_identifier
from gossip.signed_object import generate_signing_key

from journal.consensus.poet0.poet_journal import PoetJournal
from ledger.transaction import endpoint_registry
from ledger.transaction import integer_key
from txnintegration.utils import read_key_file
from sawtooth.config import ArgparseOptionsConfig
from sawtooth.validator_config import get_validator_configuration
from sawtooth.validator_config import parse_listen_directives

LOGGER = logging.getLogger(__name__)


def add_genesis_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('genesis')
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


def node_from_config(config):
    name = config['NodeName']
    signing_key = generate_signing_key(wifstr=read_key_file(config['KeyFile']))
    (gossip_host, gossip_port) = parse_listen_directives(config)['gossip']
    # stubbing endpoint address for now
    endpoint_addr = (None, None)
    nd = node.Node(address=(socket.gethostbyname(gossip_host), gossip_port),
                   identifier=generate_identifier(signing_key),
                   signingkey=signing_key,
                   name=name,
                   endpoint_address=endpoint_addr,
                   )
    return nd


def do_genesis(args):

    # Get ledger config:
    # set the default value of config because argparse 'default' in
    # combination with action='append' does the wrong thing.
    if args.config is None:
        args.config = ['txnvalidator.js']
    # convert any comma-delimited argument strings to list elements
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

    # Perform requisite overrides and validation:
    cfg['GenesisLedger'] = True
    cfg['Restore'] = False
    # should check that sigining key exists...
    # debug report
    for key, value in cfg.iteritems():
        LOGGER.debug("CONFIG: %s = %s", key, value)

    # instantiate ledger (from node)
    nd = node_from_config(cfg)
    # in future, dynamically select ledger obj based on LedgerType
    ledger = PoetJournal(nd, **cfg)
    # may need to add transaction family objects ad hoc from cfg
    dfl_txn_families = [endpoint_registry, integer_key]
    for txnfamily in dfl_txn_families:
        txnfamily.register_transaction_types(ledger)
    # ...skipping onNodeDisconnect handler (using ledger, not validator...)

    # Create genesis block:
    # we should make sure there is no current chain here, or fail
    # calling initialization_complete will create the genesis block
    ledger.initialization_complete()
    # simulate receiving the genesis block msg from reactor to force commit
    msg = ledger.MessageQueue.pop()
    (_, msg_handler) = ledger.MessageHandlerMap[msg.MessageType]
    msg_handler(msg, ledger)

    # Report, then shutdown to save state:
    head = ledger.MostRecentCommittedBlockID
    n_blks = ledger.CommittedBlockCount
    LOGGER.info('current chain head: %s; current chain len: %s', head, n_blks)
    ledger.shutdown()
    return (head, n_blks)  # return values for unit and/or integration tests

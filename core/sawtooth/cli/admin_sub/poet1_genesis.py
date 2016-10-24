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
import json

from gossip.gossip_core import Gossip
from journal.journal_core import Journal
from ledger.transaction import endpoint_registry
from ledger.transaction import integer_key
from sawtooth.cli.admin_sub.genesis_common import genesis_info_file_name
from sawtooth.config import ArgparseOptionsConfig
from sawtooth.validator_config import get_validator_configuration
from txnserver.validator import parse_networking_info

LOGGER = logging.getLogger(__name__)


def add_poet1_genesis_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('poet1-genesis')
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


def do_poet1_genesis(args):

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

    # Obtain Journal object:
    # ...set WaitTimer globals
    target_wait_time = cfg.get("TargetWaitTime")
    initial_wait_time = cfg.get("InitialWaitTime")
    certificate_sample_length = cfg.get('CertificateSampleLength')
    fixed_duration_blocks = cfg.get("FixedDurationBlocks")
    from journal.consensus.poet1.wait_timer import set_wait_timer_globals
    set_wait_timer_globals(target_wait_time,
                           initial_wait_time,
                           certificate_sample_length,
                           fixed_duration_blocks,
                           )
    # ...build Gossip dependency
    (nd, _) = parse_networking_info(cfg)
    minimum_retries = cfg.get("MinimumRetries")
    retry_interval = cfg.get("RetryInterval")
    gossiper = Gossip(nd, minimum_retries, retry_interval)
    # ...build Journal
    min_txn_per_block = cfg.get("MinimumTransactionsPerBlock")
    max_txn_per_block = cfg.get("MaxTransactionsPerBlock")
    max_txn_age = cfg.get("MaxTxnAge")
    genesis_ledger = cfg.get("GenesisLedger")
    data_directory = cfg.get("DataDirectory")
    store_type = cfg.get("StoreType")
    stat_domains = {}
    from journal.consensus.poet1.poet_consensus import PoetConsensus
    consensus_obj = PoetConsensus(cfg)
    journal = Journal(gossiper.LocalNode,
                      gossiper,
                      gossiper.dispatcher,
                      consensus_obj,
                      stat_domains,
                      minimum_transactions_per_block=min_txn_per_block,
                      max_transactions_per_block=max_txn_per_block,
                      max_txn_age=max_txn_age,
                      genesis_ledger=genesis_ledger,
                      data_directory=data_directory,
                      store_type=store_type,
                      )

    # ...add txn families (needs dynamic loading)
    dfl_txn_families = [endpoint_registry, integer_key]
    for txnfamily in dfl_txn_families:
        txnfamily.register_transaction_types(journal)

    # Make genesis block:
    # ...pop VR seed (we'll presently defer resolving VR seed issues)
    _ = gossiper.IncomingMessageQueue.pop()
    # ...create block g_block (including VR seed txn just popped)
    g_block = journal.build_block(genesis=True)  # seed later...
    journal.claim_block(g_block)
    g_block_msg = gossiper.IncomingMessageQueue.pop()
    journal.dispatcher.dispatch(g_block_msg)
    journal.initialization_complete()
    head = journal.most_recent_committed_block_id
    chain_len = len(journal.committed_block_ids())

    # Run shutdown:
    # ...persist new state
    journal.shutdown()
    # ...release gossip obj's UDP port
    gossiper.Listener.loseConnection()
    gossiper.Listener.connectionLost(reason=None)

    # Log genesis data, then write it out to ease dissemination
    genesis_data = {
        'GenesisId': head,
        'ChainLength': chain_len,
    }
    gblock_fname = genesis_info_file_name(cfg['DataDirectory'])
    LOGGER.info('genesis data: %s', genesis_data)
    LOGGER.info('writing genesis data to %s', gblock_fname)
    with open(gblock_fname, 'w') as f:
        f.write(json.dumps(genesis_data))

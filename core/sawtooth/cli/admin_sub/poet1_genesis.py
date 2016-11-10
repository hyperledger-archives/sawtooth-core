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
import importlib
import json
import logging

from gossip.gossip_core import Gossip
from journal.journal_core import Journal
from ledger.transaction import endpoint_registry
from sawtooth.cli.admin_sub.genesis_common import add_genesis_parser
from sawtooth.cli.admin_sub.genesis_common import check_for_chain
from sawtooth.cli.admin_sub.genesis_common import genesis_info_file_name
from sawtooth.cli.admin_sub.genesis_common import mirror_validator_parsing
from txnserver.validator import parse_networking_info

from sawtooth_validator.consensus.poet1.wait_timer \
    import set_wait_timer_globals
from sawtooth_validator.consensus.poet1.poet_consensus import PoetConsensus
from sawtooth_validator.consensus.poet1 import validator_registry

LOGGER = logging.getLogger(__name__)


def add_poet1_genesis_parser(subparsers, parent_parser):
    add_genesis_parser(subparsers, parent_parser, 'poet1')


def do_poet1_genesis(args):
    # Get journal config:
    cfg = mirror_validator_parsing(args)

    # Check for existing block store
    node_name = cfg.get("NodeName")
    data_directory = cfg.get("DataDirectory")
    store_type = cfg.get("StoreType")
    check_for_chain(data_directory, node_name, store_type)

    # Obtain Journal object:
    # ...set WaitTimer globals
    target_wait_time = cfg.get("TargetWaitTime")
    initial_wait_time = cfg.get("InitialWaitTime")
    certificate_sample_length = cfg.get('CertificateSampleLength')
    fixed_duration_blocks = cfg.get("FixedDurationBlocks")
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
    stat_domains = {}
    consensus_obj = PoetConsensus(cfg)
    journal = Journal(gossiper.LocalNode,
                      gossiper,
                      gossiper.dispatcher,
                      consensus_obj,
                      stat_domains,
                      minimum_transactions_per_block=min_txn_per_block,
                      max_transactions_per_block=max_txn_per_block,
                      max_txn_age=max_txn_age,
                      data_directory=data_directory,
                      store_type=store_type,
                      )
    # ...add 'built in' txn families
    default_transaction_families = [
        endpoint_registry,
        validator_registry,
    ]
    for txn_family in default_transaction_families:
        txn_family.register_transaction_types(journal)
    # ...add auxiliary transaction families
    for txn_family_module_name in cfg.get("TransactionFamilies", []):
        txn_family = importlib.import_module(txn_family_module_name)
        txn_family.register_transaction_types(journal)

    # Make genesis block:
    # ...make sure there is no current chain here, or fail
    # ...pop VR seed (we'll presently defer resolving VR seed issues)
    vr_seed = gossiper.IncomingMessageQueue.pop()
    journal.initial_transactions.append(vr_seed.Transaction)
    # ...create block g_block (including VR seed txn just popped)
    journal.on_genesis_block.fire(journal)
    journal.initializing = False
    for txn in journal.initial_transactions:
        journal.add_pending_transaction(txn, build_block=False)
    g_block = journal.build_block(genesis=True)  # seed later...
    journal.claim_block(g_block)
    # ...simulate receiving the genesis block msg from reactor to force commit
    g_block_msg = gossiper.IncomingMessageQueue.pop()
    poet_public_key = g_block.poet_public_key
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
        'PoetPublicKey': poet_public_key,
    }
    gblock_fname = genesis_info_file_name(cfg['DataDirectory'])
    LOGGER.info('genesis data: %s', genesis_data)
    LOGGER.info('writing genesis data to %s', gblock_fname)
    with open(gblock_fname, 'w') as f:
        f.write(json.dumps(genesis_data, indent=4))

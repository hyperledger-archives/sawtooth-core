#!/usr/bin/python

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

"""
A script to synchronize sawtooth bond state in a rethink database.
"""

import os
import sys
import logging
import argparse
import time
import rethinkdb
from cachetools import LRUCache

from gossip.common import NullIdentifier
from sawtooth.client import SawtoothClient

from config import ParseConfigurationFiles
from config import SetupLoggers

logger = logging.getLogger()

full_sync_interval = 50
_full_sync_counter = 0

block_cache = LRUCache(maxsize=100)


def GetCurrentBlockList(client, count):
    """
    """

    # Get the identity of the block at the head of the chain
    try:
        blocklist = client.get_block_list(count)
    except:
        logger.exception('failed to retrieve the current block list')
        return None

    return blocklist


def GetBlock(client, blockid):
    """
    Get a block from the ledger and cache it for future use

   :param SawtoothClient client: client for accessing the ledger
   :param str blockid: identifier for the current block
    """

    global block_cache
    if blockid in block_cache:
        return block_cache[blockid]

    # Get the identity of the block at the head of the chain
    try:
        block = client.get_block(block_id=blockid)
        block_cache[blockid] = block
    except:
        logger.exception('failed to retrieve block %s', blockid)
        return None

    return block


def GetPreviousBlockID(client, blockid):
    """
    Return the value of the PrevioudBlockID field from the block

   :param SawtoothClient client: client for accessing the ledger
   :param str blockid: identifier for the current block
    """
    block = GetBlock(client, blockid)
    return block.get('PreviousBlockID', NullIdentifier)


def GetBlockNum(client, blockid):
    """
    Return the value of the BlockNum field from the block

   :param SawtoothClient client: client for accessing the ledger
   :param str blockid: identifier for the current block
    """

    block = GetBlock(client, blockid)
    return int(block.get('BlockNum', -1))


def GetBlockStateDelta(client, blockid):
    """
    Get the state delta for the identified block

    :param SawtoothClient client: client for accessing the ledger
    :param str blockid: identifier for the current block
    """

    # Get the identity of the block at the head of the chain
    try:
        blockdelta = client.get_store_delta_for_block(blockid)
    except:
        logger.exception('failed to retrieve state delta for block %s',
                         blockid)
        return None

    return blockdelta


def GetBlockStateFull(client, blockid):
    """
    Get the full status for the identified block

    :param SawtoothClient client: client for accessing the ledger
    :param str blockid: identifier for the current block
    """

    # Get the state for the current block
    try:
        blockstate = client.get_store_objects_through_block(blockid)
    except:
        logger.exception('failed to retrieve the state of block %s', blockid)
        return None

    return blockstate


def GetTransaction(client, txnid):
    """
    Get data from the specified transaction

   :param SawtoothClient client: client for accessing the ledger
   :param str txnid: identifier for a transaction
    """

    try:
        txninfo = client.get_transaction(transaction_id=txnid)
    except:
        logger.exception('failed to retrieve transaction %s', txnid)
        return None

    return txninfo


def CleanupOldState(blocklist):
    """
    Remove the tables for state that are no longer necessary

   :param list blocklist: list of block identifiers
    """

    statenames = map(lambda b: 'blk' + b, blocklist)
    tablelist = rethinkdb.table_list().run()
    for table in tablelist:
        if table.startswith('blk') and table not in statenames:
            try:
                logger.info('drop old state table %s', table)
                rethinkdb.table_drop(table).run()
            except:
                logger.exception('failed to drop state table %s', table)


def SaveToBlockList(blockinfo):
    """
    Save block information to the block list table

   :param dict blockinfo: block data
    """

    logger.debug('insert block %s into block list table', blockinfo['id'])

    try:
        blktable = rethinkdb.table('block_list')
        blktable.insert(blockinfo).run()
    except:
        logger.exception('failed to insert block %s into block list',
                         blockinfo['id'])


def SaveBlockState(client, blockid):
    """
    Synchronize the current ledger state into the database. This creates a
    new table identified by the block identifier.

    :param SawtoothClient client: client for accessing the ledger
    :param str blockid: identifier for a block
    """

    # Get/create the table for the block state
    logger.debug('create state table for block %s', blockid)
    currentblockname = 'blk' + blockid
    rethinkdb.table_create(currentblockname).run()

    # Check to see if there is already a collection in the
    # database for the previous block
    previousblockid = GetPreviousBlockID(client, blockid)
    previousblockname = 'blk' + previousblockid

    assert (previousblockid == NullIdentifier or
            previousblockname in rethinkdb.table_list().run())

    # we use the full_sync_interval to ensure that we never
    # get too far away from the ledger, this shouldn't be
    # necessary and should be dropped later
    global _full_sync_counter, full_sync_interval
    _full_sync_counter -= 1

    if _full_sync_counter > 0:
        # update from the delta to the previous state
        logger.info('copy block %s from existing block %s',
                    blockid, previousblockid)

        # copy the block in the database
        rethinkdb.table(currentblockname).insert(
            rethinkdb.table(previousblockname)).run()

        # retrieve the deltas
        blockdelta = GetBlockStateDelta(client, blockid)
        if blockdelta:
            blockstate = blockdelta['Store']
            blockdeletes = blockdelta['DeletedKeys']
        else:
            blockstate = {}
            blockdeletes = []

    else:
        # perform a full state update
        logger.info('copy block %s from ledger', blockid)

        # retreive the complete state
        blockstate = GetBlockStateFull(client, blockid)
        blockdeletes = []
        _full_sync_counter = full_sync_interval

        # the only time we have the information to add the name is when
        # we have the full dump, so names may be out of data between
        # full syncs

    # And add all the objects from the current state into the new collection
    for (objid, objinfo) in blockstate.iteritems():
        objinfo['id'] = objid
        rethinkdb.table(currentblockname).get(objid).replace(objinfo).run()

    # and delete the ones we dont need
    for objid in blockdeletes:
        rethinkdb.table(currentblockname).get(objid).delete().run()


def SaveTransactions(client, blockinfo):
    """
    Save the transactions committed in a block into the transaction table

    Args:
        client -- SawtoothClient for accessing the ledger
        blockinfo -- dictionary, block data
    """

    logger.debug('save transactions for block %s in transaction table',
                 blockinfo['id'])

    # save the transactions in the block
    txnlist = []
    for txnid in blockinfo['TransactionIDs']:
        txn = GetTransaction(client, txnid)
        if txn:
            txn['id'] = txnid
            txnlist.append(txn)

    if txnlist:
        try:
            txntable = rethinkdb.table('txn_list')
            txntable.insert(txnlist).run()
        except:
            logger.exception(
                'failed to insert txns for block %s into transaction table',
                blockinfo['id'])


def UpdateTransactionState(client, ledgerblocks):
    """
    Update the state of transactions from the transaction collection in the
    exchange database.

    Args:
        client -- SawtoothClient for accessing the ledger
        ledgerblocks -- list of block identifiers in the current ledger
    """

    # add the failed block to the list so we dont keep trying to
    # fix a transaction that is marked as unfixable
    blklist = set(ledgerblocks[:])
    blklist.add('failed')

    # ok... now we are looking for any transactions that are not in
    # one of the blocks in the committed list, transactions that are
    # in one of these blocks already have the correct state registered
    # one concern about this approach is that transactions that fail
    # are likely to stick around for a long time because we don't know
    # if they might magically show up in another block, for now I'm
    # just going to assume that a transaction that fails, fails
    # permanently

    logger.debug('update transaction state from blocks')

    # this is the query that we should use, but it isn't working probably
    # because of missing InBlock fields but there are no logs to be sure
    txnquery = rethinkdb.table('transactions').filter(
        lambda doc: ~(rethinkdb.expr(blklist).contains(doc['InBlock'])))

    txniter = txnquery.run()

    for txndoc in txniter:
        txnid = txndoc.get('id')
        assert txnid

        if txndoc.get('InBlock') in blklist:
            logger.debug('already processed transaction %s', txnid)
            continue

        try:
            logger.info('update status of transaction %s', txnid)
            txn = client.get_transaction(txnid)

            txndoc['Status'] = txn['Status']
            if txn.get('InBlock'):
                txndoc['InBlock'] = txn['InBlock']

        except:
            # if we cannot retrieve the transaction then assume that it has
            # failed to commit, this might be an invalid assumption if the
            #  validator itself has failed though presumably that would have
            #  been discovered much earlier
            logger.info('failed to retrieve transaction %s, marking it failed',
                        txnid)
            txndoc['Status'] = 3
            txndoc['InBlock'] = 'failed'

        rethinkdb.table('transactions').get(txnid).replace(txndoc).run()


def AddBlock(client, blockid):
    """
    Args:
        client -- SawtoothClient for accessing the ledger
        blockid -- string, sawtooth identifier
    """

    logger.info('add block %s', blockid)

    blockinfo = GetBlock(client, blockid)
    blockinfo['id'] = blockid

    SaveToBlockList(blockinfo)
    SaveTransactions(client, blockinfo)
    SaveBlockState(client, blockid)


def DropBlock(client, blockinfo):
    """
    Drop a block and all associated data, this can happen when a block
    is removed from the committed chain by a fork.

    Args:
        client -- SawtoothClient for accessing the ledger
        blockinfo -- block data
    """

    logger.info('drop block %s', blockinfo['id'])

    try:
        rethinkdb.table('block_list').get(blockinfo['id']).delete().run()
    except:
        logger.warn('failed to remove block %s from block list table',
                    blockinfo['id'])

    try:
        blockstatetable = 'blk' + blockinfo['id']
        if blockstatetable in rethinkdb.table_list().run():
            rethinkdb.table(blockstatetable).tableDrop().run()
    except:
        logger.warn('failed to drop state table for block %s',
                    blockinfo['id'])

    for txnid in blockinfo['TransactionIDs']:
        try:
            rethinkdb.table('txn_list').get(txnid).delete().run()
        except:
            logger.warn('failed to drop transaction %s for block %s',
                        txnid, blockinfo['id'])


def SaveChainHead(client, blockid):
    """
    Record information about the current block in the metacollection document

    Args:
        client -- SawtoothClient for accessing the ledger
        blockid -- string, sawtooth identifier
    """

    blocknum = GetBlockNum(client, blockid)
    blockdoc = {'id': 'currentblock', 'blockid': blockid, 'blocknum': blocknum}

    metatable = rethinkdb.table('chain_info')
    metatable.get('currentblock').replace(blockdoc).run()


def ProcessBlockList(client, ledgerblocks):
    """
    Args:
        client -- SawtoothClient for accessing the ledger
        ledgerblocks -- list of block identifiers in the current ledger
    """

    logger.info('process new blocks')

    headblockid = ledgerblocks[0]
    statelist = ledgerblocks[:10]

    deleteblocks = []
    bcursor = rethinkdb.table('block_list').run()
    for blockinfo in bcursor:
        try:
            ledgerblocks.remove(blockinfo['id'])
        except ValueError:
            deleteblocks.append(blockinfo)

    for blockid in deleteblocks:
        DropBlock(client, blockid)

    # work through the list of new block from oldest to newest
    for blockid in reversed(ledgerblocks):
        AddBlock(client, blockid)

    SaveChainHead(client, headblockid)

    CleanupOldState(statelist)


def InitializeDatabase(dbhost, dbport, dbname):
    """
    """

    rconn = rethinkdb.connect(dbhost, dbport)
    rconn.repl()

    if dbname not in rethinkdb.db_list().run():
        logger.info('create the sync database %s', dbname)
        rethinkdb.db_create(dbname).run()

    rconn.use(dbname)

    tables = rethinkdb.table_list().run()
    for tabname in ['block_list', 'chain_info', 'txn_list']:
        if tabname not in tables:
            rethinkdb.table_create(tabname).run()

    rconn.close()


def LocalMain(config):
    """
    Main processing loop for the synchronization process
    """

    # To make this more robust we should probably pass in several
    # URLs and handle failures more cleanly by swapping to alternates
    client = SawtoothClient(config['LedgerURL'],
                            store_name='BondTransaction',
                            name='LedgerSyncClient')

    global full_sync_interval
    full_sync_interval = config.get('FullSyncInterval', 50)
    blockcount = config.get('BlockCount', 10)
    refresh = config['Refresh']

    # pull database and collection names from the configuration and set up the
    # connections that we need
    dbhost = config.get('DatabaseHost', 'localhost')
    dbport = int(config.get('DatabasePort', 28015))
    dbname = config['DatabaseName']

    InitializeDatabase(dbhost, dbport, dbname)

    lastblockid = None

    while True:
        try:
            logger.debug('begin synchronization')
            rconn = rethinkdb.connect(dbhost, dbport, dbname)
            rconn.repl()

            currentblocklist = GetCurrentBlockList(client, full_sync_interval)
            currentblockid = currentblocklist[0]

            UpdateTransactionState(client, currentblocklist)

            if currentblockid and currentblockid != lastblockid:
                ProcessBlockList(client, currentblocklist)
                logger.info('synchronization completed successfully, '
                            'current block is %s', currentblockid)

            lastblockid = currentblockid
        except:
            logger.exception('synchronization failed')
        finally:
            logger.debug('close the database connection')
            rconn.close()

        logger.debug('sleep for %s seconds', float(refresh))
        time.sleep(float(refresh))


CurrencyHost = os.environ.get("HOSTNAME", "localhost")
CurrencyHome = os.environ.get("EXPLORERHOME") or os.environ.get("CURRENCYHOME")
CurrencyEtc = (os.environ.get("EXPLORERETC") or
               os.environ.get("CURRENCYETC") or
               os.path.join(CurrencyHome, "etc"))
CurrencyLogs = (os.environ.get("EXPLORERLOGS") or
                os.environ.get("CURRENCYLOGS") or
                os.path.join(CurrencyHome, "logs"))
ScriptBase = os.path.splitext(os.path.basename(sys.argv[0]))[0]

config_map = {
    'base': ScriptBase,
    'etc': CurrencyEtc,
    'home': CurrencyHome,
    'host': CurrencyHost,
    'logs': CurrencyLogs
}


def ParseCommandLine(config, args):
    parser = argparse.ArgumentParser()

    help_text = 'Name of the log file, __screen__ for standard output',
    parser.add_argument('--logfile',
                        help=help_text,
                        default=config.get('LogFile', '__screen__'))

    parser.add_argument('--loglevel',
                        help='Logging level',
                        default=config.get('LogLevel', 'INFO'))

    parser.add_argument('--url',
                        help='Default url for connection to the ledger',
                        default=config.get('LedgerURL',
                                           'http://localhost:8800'))

    parser.add_argument('--dbhost',
                        help='Host where the rethink db resides',
                        default=config.get('DatabaseHost', 'localhost'))

    parser.add_argument('--dbport',
                        help='Port where the rethink db listens',
                        default=config.get('DatabasePort', 28015))

    help_text = 'Name of the rethink database where data will be stored'
    parser.add_argument('--dbname',
                        help=help_text,
                        default=config.get('DatabaseName', 'ledger'))

    parser.add_argument('--refresh',
                        help='Number of seconds between ledger probes',
                        default=config.get('Refresh', 10))

    parser.add_argument('--set',
                        help='Specify arbitrary configuration options',
                        nargs=2,
                        action='append')

    options = parser.parse_args(args)

    config["LogLevel"] = options.loglevel.upper()
    config["LogFile"] = options.logfile

    config['DatabaseHost'] = options.dbhost
    config['DatabasePort'] = options.dbport
    config['DatabaseName'] = options.dbname
    config['Refresh'] = options.refresh
    config["LedgerURL"] = options.url

    if options.set:
        for (k, v) in options.set:
            config[k] = v


def Main():
    # parse out the configuration file first
    conf_file = ScriptBase + '.js'
    conf_path = [".", "./etc", CurrencyEtc]

    parser = argparse.ArgumentParser()
    parser.add_argument('--config',
                        help='configuration file',
                        default=[conf_file],
                        nargs='+')
    parser.add_argument('--config-dir',
                        help='configuration file',
                        default=conf_path,
                        nargs='+')
    (options, remainder) = parser.parse_known_args()

    config = ParseConfigurationFiles(options.config,
                                     options.config_dir,
                                     config_map)

    ParseCommandLine(config, remainder)

    SetupLoggers(config)

    LocalMain(config)

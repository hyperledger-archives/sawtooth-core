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
@file   syncledger.py
@author	Mic Bowman
@date	2016-03-14
@status	RESEARCH PROTOTYPE

A script to synchronize marketplace ledger state in a rethink database.
"""

import os
import sys
import logging
import argparse
import rethinkdb

from config import ParseConfigurationFiles

logger = logging.getLogger()


def LocalMain(config):
    """
    Main processing loop for the synchronization process
    """

    # pull database and collection names from the configuration and set up the
    # connections that we need
    dbhost = config.get('DatabaseHost', 'localhost')
    dbport = int(config.get('DatabasePort', 28015))
    dbname = config['DatabaseName']

    rconn = rethinkdb.connect(dbhost, dbport)
    rconn.repl()
    rconn.use(dbname)

    tablelist = rethinkdb.table_list().run()
    for table in tablelist:
        try:
            logger.info('drop table %s', table)
            rethinkdb.table_drop(table).run()
        except:
            logger.exception('failed to drop table %s', table)

    rconn.close()


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

    help_text = 'Name of the log file, __screen__ for standard output'
    parser.add_argument('--logfile',
                        help=help_text,
                        default=config.get('LogFile', '__screen__'))
    parser.add_argument('--loglevel',
                        help='Logging level',
                        default=config.get('LogLevel', 'INFO'))

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

    if options.set:
        for (k, v) in options.set:
            config[k] = v


def Main():
    # parse out the configuration file first
    conffile = ScriptBase + '.js'
    confpath = [".", "./etc", CurrencyEtc]

    parser = argparse.ArgumentParser()
    parser.add_argument('--config',
                        help='configuration file',
                        default=[conffile],
                        nargs='+')
    parser.add_argument('--config-dir',
                        help='configuration file',
                        default=confpath,
                        nargs='+')
    (options, remainder) = parser.parse_known_args()

    config = ParseConfigurationFiles(options.config,
                                     options.config_dir,
                                     config_map)

    ParseCommandLine(config, remainder)

    LocalMain(config)

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

import argparse
import cmd
import os
import re
import socket
import sys
import logging

from gossip.common import pretty_print_dict

from gossip.config import ArgparseOptionsConfig
from gossip.config import ConfigFileNotFound
from gossip.config import InvalidSubstitutionKey

from gossip.messages import gossip_debug
from gossip.messages import shutdown_message

from gossip.node import Node

from gossip.signed_object import generate_identifier
from gossip.signed_object import generate_signing_key

from journal.consensus.quorum.messages import quorum_debug

from journal.messages import journal_debug

from ledger.transaction import integer_key
from ledger.transaction import endpoint_registry

from txnserver import ledger_web_client, log_setup
from txnserver.config import get_validator_configuration

logger = logging.getLogger(__name__)

CurrencyHost = os.environ.get("HOSTNAME", "localhost")

TransactionTypes = {
    'endpoint': endpoint_registry.EndpointRegistryTransaction,
    'integerkey': integer_key.IntegerKeyTransaction
}


class ClientController(cmd.Cmd):
    _TxnVerbMap = {'=': 'set', '+=': 'inc', '-=': 'dec'}
    pformat = 'client> '

    def __init__(self, baseurl, keystring=None):
        cmd.Cmd.__init__(self)
        self.prompt = 'client> '
        self.CurrentState = {}
        self.LedgerWebClient = ledger_web_client.LedgerWebClient(baseurl)

        signingkey = generate_signing_key(
            wifstr=keystring) if keystring else generate_signing_key()
        identifier = generate_identifier(signingkey)
        self.LocalNode = Node(identifier=identifier,
                              signingkey=signingkey,
                              name="txnclient")

    def postcmd(self, flag, line):
        return flag

    def sign_and_post(self, msg):
        msg.SenderID = self.LocalNode.Identifier
        msg.sign_from_node(self.LocalNode)

        try:
            result = self.LedgerWebClient.post_message(msg)
            if result:
                pretty_print_dict(result)

        except ledger_web_client.MessageException as me:
            print me

    # =================================================================
    # COMMANDS
    # =================================================================

    def do_set(self, args):
        """
        set -- Command to set properties of the interpreter
            set url --url <url>
            set nodeid --name <name> --keyfile <file>
        """

        pargs = args.split()
        if len(pargs) == 0:
            print 'missing subcommand url|nodeid'
            return

        try:
            if pargs[0] == 'url':
                parser = argparse.ArgumentParser()
                parser.add_argument('--url',
                                    help='url used to connect to a validator',
                                    required=True)
                options = parser.parse_args(pargs)

                self.BaseURL = options.url
                print "server URL set to {0}".format(self.BaseURL)
                return

            elif pargs[0] == 'nodeid':
                pargs = args.split()
                parser = argparse.ArgumentParser()
                parser.add_argument('--name',
                                    help='name to use for the client',
                                    default='txnclient')
                parser.add_argument('--keyfile',
                                    help='name of the file that contains '
                                         'the wif format private key')
                options = parser.parse_args(pargs[1:])

                addr = (socket.gethostbyname("localhost"), 0)
                name = options.name
                if options.keyfile:
                    signingkey = generate_signing_key(
                        wifstr=read_key_file(options.keyfile))
                else:
                    signingkey = generate_signing_key()

                identifier = generate_identifier(signingkey)

                self.LocalNode = Node(address=addr,
                                      identifier=identifier,
                                      signingkey=signingkey,
                                      name=name)
                print "local id set to {0}".format(self.LocalNode)
                return

            else:
                print "unknown subcommand; {0}".format(pargs[0])
                return

        except Exception as e:
            print 'an error occured processing {0}: {1}'.format(args, str(e))
            return

    def do_state(self, args):
        """
        state -- Command to manipulate the current ledger state
            state fetch --store <store>
            state keys
            state value --path <path>
        """

        pargs = args.split()
        if len(pargs) == 0:
            print 'missing subcommand: fetch|keys|value'
            return

        try:
            if pargs[0] == 'fetch':
                parser = argparse.ArgumentParser()
                parser.add_argument('--store',
                                    choices=TransactionTypes.keys(),
                                    default='endpoint')
                options = parser.parse_args(pargs[1:])

                self.CurrentState = self.LedgerWebClient.get_store(
                    TransactionTypes.get(options.store),
                    key='*')

            elif pargs[0] == 'keys':
                try:
                    print self.CurrentState.keys()
                except:
                    print '[]'

            elif pargs[0] == 'value':
                parser = argparse.ArgumentParser()
                parser.add_argument('--path', required=True)
                options = parser.parse_args(pargs[1:])
                pathargs = options.path.split('.')
                value = self.CurrentState
                while pathargs:
                    value = value.get(pathargs.pop(0))

                print value

        except Exception as e:
            print 'an error occured processing {0}: {1}'.format(args, str(e))
            return

    def do_txn(self, args):
        """
        txn -- Command to create IntegerKey transactions
            txn <expr> [ && <expr> ]*
        """
        txn = integer_key.IntegerKeyTransaction()

        # pylint: disable=line-too-long
        pattern = re.compile(r"^\s*(?P<name>[a-zA-Z0-9]+)\s*(?P<verb>[+-]?=)\s*(?P<value>[0-9]+)\s*$")  # noqa
        expressions = args.split('&&')
        for expression in expressions:
            match = pattern.match(expression)
            if not match:
                print 'unable to parse the transaction; {0}'.format(expression)
                return

            update = integer_key.Update()
            update.Verb = self._TxnVerbMap[match.group('verb')]
            update.Name = match.group('name')
            update.Value = long(match.group('value'))
            txn.Updates.append(update)

        txn.sign_from_node(self.LocalNode)

        msg = integer_key.IntegerKeyTransactionMessage()
        msg.Transaction = txn

        self.sign_and_post(msg)

    def do_nodestats(self, args):
        """
        nodestats -- Command to send nodestats messages to validator pool
            nodestats reset --metrics [<metric>]+
            nodestats dump --metrics [<metric>]+ --domains [<domain>]+
        """

        pargs = args.split()
        if len(pargs) == 0:
            print 'missing subcommand: reset|dump'
            return

        try:
            if pargs[0] == 'reset':
                parser = argparse.ArgumentParser()
                parser.add_argument('--metrics', default=[], nargs='+')
                options = parser.parse_args(pargs[1:])

                self.sign_and_post(gossip_debug.ResetStatsMessage(
                    {'MetricList': options.metrics}))
                return

            elif pargs[0] == 'dump':
                parser = argparse.ArgumentParser()
                parser.add_argument('--metrics', default=[], nargs='+')
                parser.add_argument('--domains', default=[], nargs='+')
                options = parser.parse_args(pargs[1:])

                self.sign_and_post(gossip_debug.DumpNodeStatsMessage(
                    {'MetricList': options.metrics,
                     'DomainList': options.domains}))
                return

        except Exception as e:
            print 'an error occured processing {0}: {1}'.format(args, str(e))
            return

        print 'unknown nodestats command {0}'.format(args)

    def do_peerstats(self, args):
        """
        peerstats -- Command to send peerstats messages to validator pool
            peerstats reset --metrics [<metric>]+
            peerstats dump --metrics [<metric>]+ --peers [<nodeid>]+
        """

        pargs = args.split()
        if len(pargs) == 0:
            print 'missing subcommand: reset|dump'
            return

        try:
            if pargs[0] == 'reset':
                parser = argparse.ArgumentParser()
                parser.add_argument('--metrics', default=[], nargs='+')
                options = parser.parse_args(pargs[1:])

                self.sign_and_post(gossip_debug.ResetPeerStatsMessage(
                    {'MetricList': options.metrics}))
                return

            elif pargs[0] == 'dump':
                parser = argparse.ArgumentParser()
                parser.add_argument('--metrics', default=[], nargs='+')
                parser.add_argument('--peers', default=[], nargs='+')
                options = parser.parse_args(pargs[1:])

                self.sign_and_post(gossip_debug.DumpPeerStatsMessage(
                    {'MetricList': options.metrics,
                     'PeerIDList': options.peers}))
                return

        except Exception as e:
            print 'an error occured processing {0}: {1}'.format(args, str(e))
            return

        print 'unknown peerstats command {0}'.format(args)

    def do_ping(self, args):
        """
        ping -- Command to send a ping message to validator pool
        """

        self.sign_and_post(gossip_debug.PingMessage({}))

    def do_dumpquorum(self, args):
        """
        dumpquorum -- Command to request quorum consensus node to dump quorum
            list
        """

        self.sign_and_post(quorum_debug.DumpQuorumMessage({}))

    def do_dumpcnxs(self, args):
        """
        dumpcnxs -- Command to send to the validator pool a request to dump
            current connection information
        """

        self.sign_and_post(gossip_debug.DumpConnectionsMessage({}))

    def do_dumpblks(self, args):
        """
        dumpblks -- Command to send dump blocks request to the validator pool
            dumpblks --blocks <count>
        """

        parser = argparse.ArgumentParser()
        parser.add_argument('--blocks', default=0, type=int)
        options = parser.parse_args(args.split())

        self.sign_and_post(gossip_debug.DumpJournalBlocksMessage(
            {'Count': options.blocks}))

    def do_val(self, args):
        """
        val -- Command to send a dump value request to the validator pool
            val <name> [--type <transaction type>]
        """

        pargs = args.split()
        parser = argparse.ArgumentParser()
        parser.add_argument('--type',
                            help='Transaction family',
                            default='/IntegerKeyTransaction')
        options = parser.parse_args(pargs[1:])

        tinfo = {'Name': pargs[0], 'TransactionType': options.type}

        self.sign_and_post(journal_debug.DumpJournalValueMessage(tinfo))

    def do_shutdown(self, args):
        """
        shutdown -- Command to send a shutdown message to the validator pool
        """

        self.sign_and_post(shutdown_message.ShutdownMessage({}))
        return True

    def do_exit(self, args):
        """exit
        Shutdown the simulator and exit the command loop
        """
        return True

    def do_eof(self, args):
        return True


def local_main(config):
    controller = ClientController(config['LedgerURL'],
                                  keystring=config.get('SigningKey'))
    controller.cmdloop()


def parse_command_line(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--config',
                        help='configuration file',
                        default=['txnclient.js'],
                        nargs='+')
    parser.add_argument('--loglevel', help='Logging level')
    parser.add_argument('--keyfile', help='Name of the key file')
    parser.add_argument('--conf-dir', help='Name of the config directory')
    parser.add_argument('--log-dir', help='Name of the log directory')
    parser.add_argument(
        '--logfile',
        help='Name of the log file, __screen__ for standard output',
        default='__screen__')
    parser.add_argument('--url', help='Initial URL for the validator')
    parser.add_argument('--node', help='Short form name of the node')
    parser.add_argument('--set',
                        help='Specify arbitrary configuration options',
                        nargs=2,
                        action='append')

    return parser.parse_args(args)


def get_configuration(args, os_name=os.name, config_files_required=True):
    options = parse_command_line(args)

    options_config = ArgparseOptionsConfig(
        [
            ('loglevel', 'LogLevel'),
            ('keyfile', 'KeyFile'),
            ('conf_dir', 'ConfigDirectory'),
            ('log_dir', 'LogDirectory'),
            ('logfile', 'LogFile'),
            ('url', 'LedgerURL'),
            ('node', 'NodeName'),
        ], options)

    if "LogLevel" in options_config:
        options_config["LogLevel"] = options_config["LogLevel"].upper()

    return get_validator_configuration(options.config, options_config, os_name,
                                       config_files_required)


def read_key_file(keyfile):
    with open(keyfile, "r") as fd:
        key = fd.read().strip()
    return key


def main(args=sys.argv[1:]):
    try:
        cfg = get_configuration(args)
    except ConfigFileNotFound, e:
        print >> sys.stderr, str(e)
        sys.exit(1)
    except InvalidSubstitutionKey, e:
        print >> sys.stderr, str(e)
        sys.exit(1)

    log_setup.setup_loggers(cfg)

    if "KeyFile" in cfg:
        keyfile = cfg["KeyFile"]
        if os.path.isfile(keyfile):
            logger.info('read signing key from %s', keyfile)
            key = read_key_file(keyfile)
            cfg['SigningKey'] = key
        else:
            logger.warn('unable to find key file %s', keyfile)
    else:
        logger.warn('no key file specified')

    local_main(cfg)

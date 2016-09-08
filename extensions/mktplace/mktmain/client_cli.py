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
import json
import yaml
import logging.config
import os
import shlex
import sys
import time
from string import Template

from colorlog import ColoredFormatter

import pybitcointools

from gossip.common import pretty_print_dict
from mktplace import mktplace_client, mktplace_state, mktplace_token_store
from mktplace.mktplace_config import get_mktplace_configuration
from sawtooth.config import ArgparseOptionsConfig
from sawtooth.config import ConfigFileNotFound
from sawtooth.config import InvalidSubstitutionKey

logger = logging.getLogger(__name__)


def create_console_handler(verbose_level):
    clog = logging.StreamHandler()
    formatter = ColoredFormatter(
        "%(log_color)s[%(asctime)s %(levelname)-8s%(module)s]%(reset)s "
        "%(white)s%(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        })

    clog.setFormatter(formatter)

    if verbose_level == 0:
        clog.setLevel(logging.WARN)
    elif verbose_level == 1:
        clog.setLevel(logging.INFO)
    else:
        clog.setLevel(logging.DEBUG)

    return clog


def setup_loggers(verbose_level=0):
    logger = logging.getLogger()

    if verbose_level > 0:
        logger.addHandler(create_console_handler(verbose_level))


class ClientController(cmd.Cmd):
    def __init__(self, client, echo=False):
        cmd.Cmd.__init__(self)
        self.echo = echo
        self.MarketClient = client
        self.MarketState = client.CurrentState

        if self.MarketClient.CreatorID:
            self.prompt = self.MarketState.i2n(
                self.MarketClient.CreatorID) + '> '
        else:
            self.prompt = '//UNKNOWN> '

        self.IdentityMap = {
            '_partid_': self.MarketClient.CreatorID,
            '_name_': self.MarketState.i2n(self.MarketClient.CreatorID)
        }

    def precmd(self, line):
        if self.echo:
            print line
        return line

    def postcmd(self, flag, line):
        return flag

    def _expandargs(self, argstring):
        try:
            template = Template(argstring)
            return template.substitute(self.IdentityMap)
        except KeyError as ke:
            print 'missing index variable {0}'.format(ke)
            return '-h'

    def _finish(self, txnid, waitforcommit):
        if not txnid:
            print 'failed to create transaction'
            return

        print 'transaction {0} submitted'.format(txnid)

        # and wait to exit until everything is done
        if waitforcommit:
            print 'Wait for commit'
            self.MarketClient.waitforcommit()

    def help_names(self):
        print """
The name can take one of these forms:
    @ -- resolves to the identifier for creator
    ///<IDENTIFIER>  -- resolves to the identifier, this will be a transaction
        id like (///736d8deea434abb8)
    //<CREATOR>/<NAME> -- fully qualified name - Creator is the name of the
        participant followed by the name of object (//bob/asset)
    /<PATH> -- resolve relative to the current creator if specified.
        """

    def help_symbols(self):
        print """
Variable symbols can be created and stored in the client session. Symbols are
names that can be used as in the parameters of other commands that will be
expanded to there value.

Create a symbol:
    map --symbol <name> --value <value>
Show the current value of a symbol:
    echo $<name>
Use of symbol
    $<name> may be substituted for any name parameter on any command.

Many commands take a --symbol argument that map the transaction id to the
symbol specified. Those may be used as name inputs to other commands as
identifiers, ///$name

        """

    # =================================================================
    # COMMANDS
    # =================================================================

    def do_sleep(self, args):
        """
        sleep <seconds> -- command to pause processing for a time (seconds).
        """

        pargs = shlex.split(self._expandargs(args))
        if len(pargs) == 0:
            print 'Time to sleep required: sleep <seconds>'
            return

        try:
            tm = int(pargs[0])
            print "Sleeping for {} seconds".format(tm)
            time.sleep(tm)
        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_waitforcommit(self, args):
        """
        wait -- wait for a transaction to commit
        """

        pargs = shlex.split(self._expandargs(args))

        try:
            parser = argparse.ArgumentParser(prog='Wait')
            parser.add_argument(
                '--txn',
                help='Txn identifier, defaults to last submitted transaction',
                default=self.MarketClient.LastTransaction)
            options = parser.parse_args(pargs)

            if options.txn:
                print "Waiting for {}.".format(options.txn)
                if self.MarketClient.waitforcommit(options.txn):
                    print "Transaction committed."
                else:
                    print "Wait failed."
            else:
                print "No transaction specified to wait for."

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_map(self, args):
        """
        map -- assign a value to a symbol that can be retrieved with a
            $expansion
        """

        pargs = shlex.split(self._expandargs(args))

        try:
            parser = argparse.ArgumentParser(prog='map')
            parser.add_argument('--symbol',
                                help='symbol in which to store the identifier',
                                required=True)
            parser.add_argument('--value', help='identifier', required=True)
            options = parser.parse_args(pargs)

            self.IdentityMap[options.symbol] = options.value
            print "${} = {}".format(options.symbol, options.value)
            return
        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_echo(self, args):
        """
        echo -- expand local $symbols
        """
        print self._expandargs(args)

    def do_dump(self, args):
        """
        dump -- display information about an object
        """
        pargs = shlex.split(self._expandargs(args))

        try:
            parser = argparse.ArgumentParser(prog='dump')
            parser.add_argument('--name', help='name of the object')
            parser.add_argument('--fields',
                                help='Space separated list of fields to dump',
                                nargs='+')
            options = parser.parse_args(pargs)

            objectid = self.MarketState.n2i(options.name)
            if objectid and objectid in self.MarketState.State:
                if options.fields:
                    for fld in options.fields:
                        print self.MarketState.State[objectid][fld]
                else:
                    print pretty_print_dict(self.MarketState.State[objectid])
            else:
                print "Object {} not found.".format(options.name)

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_tokenstore(self, args):
        """
        tokenstore -- set the token store used to pay for transactions
        """
        pargs = shlex.split(self._expandargs(args))

        subcommands = ['holding']
        if len(pargs) == 0 or pargs[0] not in subcommands:
            print 'Unknown sub-command, expecting one of {0}'.format(
                subcommands)
            return

        try:
            if pargs[0] == 'holding':
                parser = argparse.ArgumentParser(prog='tokenstore')
                parser.add_argument('--name',
                                    help='Fully qualified name of the '
                                         'holding used to store the '
                                         'validation tokens')
                parser.add_argument('--count',
                                    help='Number of tokens to use per '
                                         'transaction',
                                    default=1)
                options = parser.parse_args(pargs[1:])

                holdingid = self.MarketState.n2i(options.name)
                self.MarketClient.TokenStore = \
                    mktplace_token_store.HoldingStore(
                        self.MarketClient.CreatorID, options.count, holdingid)

                return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_state(self, args):
        """
        state -- access elements of the state
            state fetch -- retrieve the current version of the ledger state
            state value -- get the value associated with a field in state
            state query -- find object that match specific criteria
            state byname -- find the identifier for an object using its fully
            qualified name
        """
        pargs = shlex.split(self._expandargs(args))

        subcommands = ['byname', 'fetch', 'query', 'value']
        if len(pargs) == 0 or pargs[0] not in subcommands:
            print 'Unknown sub-command, expecting one of {0}'.format(
                subcommands)
            return

        try:
            if pargs[0] == 'fetch':
                self.MarketState.fetch()
                print "State Updated."
            elif pargs[0] == 'value':
                parser = argparse.ArgumentParser(prog='state value')
                parser.add_argument('--path', required=True)
                options = parser.parse_args(pargs[1:])

                result = self.MarketState.path(options.path)
                if result:
                    print result
                else:
                    print "{} not found.".format(options.path)

            elif pargs[0] == 'query':
                parser = argparse.ArgumentParser(prog='state query')
                parser.add_argument('--type',
                                    help="Name of object type, e.g. Holding")
                parser.add_argument('--creator', help='Name of the creator')
                parser.add_argument('--name', help='Name of the object')
                parser.add_argument(
                    '--fields',
                    help='Space separated list of fields to report',
                    nargs='+')
                options = parser.parse_args(pargs[1:])

                if options.fields and '*' in options.fields:
                    fields = '*'
                else:
                    fields = options.fields
                creatorid = self.MarketState.n2i(
                    options.creator) if options.creator else None
                result = self.MarketState.list(options.type, creatorid,
                                               options.name, fields)
                if result:
                    print pretty_print_dict(result)
                else:
                    print "No objects found matching the criteria."

            elif pargs[0] == 'byname':
                parser = argparse.ArgumentParser(prog='state byname')
                parser.add_argument('--name',
                                    help='Fully qualified name for an object',
                                    required=True)
                parser.add_argument(
                    '--symbol',
                    help='Symbol to associate with the newly created id')
                options = parser.parse_args(pargs[1:])

                objectid = self.MarketState.n2i(options.name)
                if objectid:
                    if options.symbol:
                        self.IdentityMap[options.symbol] = objectid
                    else:
                        print objectid
                else:
                    print "No objects found matching the criteria."

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_exchange(self, args):
        """
        exchange -- execute an marketplace exchange transaction
        """
        pargs = shlex.split(self._expandargs(args))

        try:
            parser = argparse.ArgumentParser(prog='exchange')
            parser.add_argument('--src',
                                help='Name of the holding from which to '
                                     'draw assets, (input to the '
                                     'transaction, what you pay)',
                                required=True)
            parser.add_argument('--dst',
                                help='Name of the holding in which to '
                                     'deposit resulting assets, (output '
                                     'to the transaction, what you get) ',
                                required=True)
            parser.add_argument('--count',
                                help='Number of assets to transfer from '
                                     'the source holding. (How much do you '
                                     'want to pay?)',
                                required=True)
            parser.add_argument('--offers',
                                help='Ordered list of names of offers to '
                                     'include in the transaction',
                                nargs='+',
                                default=[])
            parser.add_argument('--waitforcommit',
                                help='Wait for transaction to commit before '
                                     'returning',
                                action='store_true')
            options = parser.parse_args(pargs)

            srcid = self.MarketState.n2i(options.src)
            dstid = self.MarketState.n2i(options.dst)

            offerids = []
            for offer in options.offers:
                offerids.append(self.MarketState.n2i(offer))

            txnid = self.MarketClient.exchange(srcid, dstid,
                                               int(options.count), offerids)

            self._finish(txnid, options.waitforcommit)
            return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_account(self, args):
        """
        account -- register or unregister an account
            account reg -- register a new account
            account unr -- unregister an existing account
        """
        pargs = shlex.split(self._expandargs(args))

        subcommands = ['reg', 'unr']
        if len(pargs) == 0 or pargs[0] not in subcommands:
            print 'Unknown sub-command, expecting one of {0}'.format(
                subcommands)
            return

        try:
            parser = argparse.ArgumentParser(prog='account reg|unr')
            parser.add_argument(
                '--waitforcommit',
                help='Wait for transaction to commit before returning',
                action='store_true')

            if pargs[0] == 'reg':
                parser.add_argument('--name',
                                    help='Name of the asset',
                                    default='')
                parser.add_argument('--description',
                                    help='Description of the asset',
                                    default='')
                parser.add_argument(
                    '--symbol',
                    help='Symbol to associate with the newly created id')
                options = parser.parse_args(pargs[1:])

                txnid = self.MarketClient.register_account(options.name,
                                                           options.description)
                if txnid and options.symbol:
                    self.IdentityMap[options.symbol] = txnid
                    print "${} = {}".format(options.symbol, txnid)

            elif pargs[0] == 'unr':
                parser.add_argument('--name',
                                    help='Fully qualified name',
                                    required=True)
                options = parser.parse_args(pargs[1:])

                objectid = self.MarketState.n2i(options.name)
                txnid = self.MarketClient.unregister_account(objectid)

            self._finish(txnid, options.waitforcommit)
            return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_asset(self, args):
        """
        asset -- register or unregister an asset
            asset reg -- register the asset
            asset unr -- unregister the asset
        """
        pargs = shlex.split(self._expandargs(args))

        subcommands = ['reg', 'unr']
        if len(pargs) == 0 or pargs[0] not in subcommands:
            print 'Unknown sub-command, expecting one of {0}'.format(
                subcommands)
            return

        try:
            parser = argparse.ArgumentParser(prog='asset reg|unr')
            parser.add_argument(
                '--waitforcommit',
                help='Wait for transaction to commit before returning',
                action='store_true')

            if pargs[0] == 'reg':
                rparser = parser.add_mutually_exclusive_group(required=False)
                rparser.add_argument(
                    '--restricted',
                    dest='restricted',
                    help='Limit asset creation to the asset owner',
                    action='store_true')
                rparser.add_argument(
                    '--no-restricted',
                    dest='restricted',
                    help='Limit asset creation to the asset owner',
                    action='store_false')
                parser.set_defaults(restricted=True)

                cparser = parser.add_mutually_exclusive_group(required=False)
                cparser.add_argument('--consumable',
                                     dest='consumable',
                                     help='Assets may not be copied',
                                     action='store_true')
                cparser.add_argument('--no-consumable',
                                     dest='consumable',
                                     help='Assets may be copied infinitely',
                                     action='store_false')
                parser.set_defaults(consumable=True)

                dparser = parser.add_mutually_exclusive_group(required=False)
                dparser.add_argument(
                    '--divisible',
                    dest='divisible',
                    help='Fractional portions of an asset are acceptable',
                    action='store_true')
                dparser.add_argument('--no-divisible',
                                     dest='divisible',
                                     help='Assets may not be divided',
                                     action='store_false')
                parser.set_defaults(divisible=False)

                parser.add_argument('--description',
                                    help='Description of the asset',
                                    default='')
                parser.add_argument('--name',
                                    help='Relative name, must begin with /',
                                    default='')
                parser.add_argument('--type',
                                    help='Fully qualified asset type name',
                                    required=True)
                parser.add_argument(
                    '--symbol',
                    help='Symbol to associate with the newly created id')
                options = parser.parse_args(pargs[1:])

                typeid = self.MarketState.n2i(options.type)
                kwargs = {}
                if options.name:
                    kwargs['name'] = options.name
                if options.description:
                    kwargs['description'] = options.description
                kwargs['restricted'] = options.restricted
                kwargs['consumable'] = options.consumable
                kwargs['divisible'] = options.divisible

                txnid = self.MarketClient.register_asset(typeid, **kwargs)
                if txnid and options.symbol:
                    self.IdentityMap[options.symbol] = txnid
                    print "${} = {}".format(options.symbol, txnid)

            elif pargs[0] == 'unr':
                parser.add_argument('--name',
                                    help='fully qualified name',
                                    required=True)
                options = parser.parse_args(pargs[1:])

                objectid = self.MarketState.n2i(options.name)
                txnid = self.MarketClient.unregister_asset(objectid)

            self._finish(txnid, options.waitforcommit)
            return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_assettype(self, args):
        """
        assettype -- register or unregister an asset type
            assettype reg -- register the asset type
            assettype unr -- unregister the asset type
        """
        pargs = shlex.split(self._expandargs(args))

        subcommands = ['reg', 'unr']
        if len(pargs) == 0 or pargs[0] not in subcommands:
            print 'Unknown sub-command, expecting one of {0}'.format(
                subcommands)
            return

        try:
            parser = argparse.ArgumentParser(prog='assettype reg|unr')
            parser.add_argument(
                '--waitforcommit',
                help='Wait for transaction to commit before returning',
                action='store_true')

            if pargs[0] == 'reg':
                rparser = parser.add_mutually_exclusive_group(required=False)
                rparser.add_argument(
                    '--restricted',
                    dest='restricted',
                    help='Limit asset creation to the asset owner',
                    action='store_true')
                rparser.add_argument(
                    '--no-restricted',
                    dest='restricted',
                    help='Permit anyone to create assets of the type',
                    action='store_false')
                parser.set_defaults(restricted=True)

                parser.add_argument('--description',
                                    help='Description of the asset',
                                    default='')
                parser.add_argument('--name',
                                    help='Relative name, must being with /',
                                    default='')
                parser.add_argument(
                    '--symbol',
                    help='Symbol to associate with the newly created id')
                options = parser.parse_args(pargs[1:])

                kwargs = {}
                if options.name:
                    kwargs['name'] = options.name
                if options.description:
                    kwargs['description'] = options.description
                kwargs['restricted'] = options.restricted

                txnid = self.MarketClient.register_assettype(**kwargs)
                if txnid and options.symbol:
                    self.IdentityMap[options.symbol] = txnid
                    print "${} = {}".format(options.symbol, txnid)

            elif pargs[0] == 'unr':
                parser.add_argument('--name',
                                    help='fully qualified name',
                                    required=True)
                options = parser.parse_args(pargs[1:])

                objectid = self.MarketState.n2i(options.name)
                txnid = self.MarketClient.unregister_assettype(objectid)

            self._finish(txnid, options.waitforcommit)
            return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_exchangeoffer(self, args):
        """
        exchangeoffer -- register or unregister an exchange offer
            exchangeoffer reg -- register a new exchange offer
            exchangeoffer unr -- unregister an existing exchange offer
        """
        pargs = shlex.split(self._expandargs(args))

        subcommands = ['reg', 'unr']
        if len(pargs) == 0 or pargs[0] not in subcommands:
            print 'Unknown sub-command, expecting one of {0}'.format(
                subcommands)
            return

        try:
            parser = argparse.ArgumentParser(prog='exchangeoffer reg|unr')
            parser.add_argument(
                '--waitforcommit',
                help='Wait for transaction to commit before returning',
                action='store_true')

            if pargs[0] == 'reg':
                parser.add_argument('--input',
                                    help='Name of the input '
                                         'liability/holding. (What you are '
                                         'offering to pay)',
                                    required=True)
                parser.add_argument('--output',
                                    help='Name of the output holding. (What '
                                         'you are offering to sell)',
                                    required=True)
                parser.add_argument('--ratio',
                                    help='Ratio of input to output instances '
                                         'as src dst',
                                    nargs=2,
                                    type=int,
                                    default=(1, 1))
                parser.add_argument('--name',
                                    help='Name to assign to the new offer',
                                    type=str)
                parser.add_argument('--description',
                                    help='Description of the offer',
                                    type=str)
                parser.add_argument('--modifier',
                                    help='Set additional behaviors on offer '
                                         'execution',
                                    choices=('Any',
                                             'ExecuteOnce',
                                             'ExecuteOncePerParticipant'))
                parser.add_argument('--minimum',
                                    help='Minimum number of assets that can '
                                         'be transferred into the offer',
                                    type=int)
                parser.add_argument('--maximum',
                                    help='Maximum number of assets that can '
                                         'be transferred into the offer',
                                    type=int)
                parser.add_argument('--symbol',
                                    help='Symbol to associate with the newly '
                                         'created id')
                options = parser.parse_args(pargs[1:])

                inputid = self.MarketState.n2i(options.input)
                outputid = self.MarketState.n2i(options.output)

                kwargs = {}
                if options.name:
                    kwargs['name'] = options.name
                if options.description:
                    kwargs['description'] = options.description
                if options.minimum:
                    kwargs['minimum'] = int(options.minimum)
                if options.maximum:
                    kwargs['maximum'] = int(options.maximum)
                if options.modifier:
                    kwargs['execution'] = options.modifier

                ratio = float(options.ratio[1]) / float(options.ratio[0])
                txnid = self.MarketClient.register_exchangeoffer(
                    inputid, outputid, ratio, **kwargs)
                if txnid and options.symbol:
                    self.IdentityMap[options.symbol] = txnid
                    print "${} = {}".format(options.symbol, txnid)

            elif pargs[0] == 'unr':
                parser.add_argument('--name',
                                    help='Fully qualified name',
                                    required=True)
                options = parser.parse_args(pargs[1:])

                objectid = self.MarketState.n2i(options.name)
                txnid = self.MarketClient.unregister_exchangeoffer(objectid)

            self._finish(txnid, options.waitforcommit)
            return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_holding(self, args):
        """
        holding -- register or unregister a holding
            holding reg -- register a new holding
            holding unr -- unregister an existing holding
        """
        pargs = shlex.split(self._expandargs(args))

        subcommands = ['reg', 'unr']
        if len(pargs) == 0 or pargs[0] not in subcommands:
            print 'Unknown sub-command, expecting one of {0}'.format(
                subcommands)
            return

        try:
            parser = argparse.ArgumentParser(prog='holding reg|unr')
            parser.add_argument(
                '--waitforcommit',
                help='Wait for transaction to commit before returning',
                action='store_true')

            if pargs[0] == 'reg':
                parser.add_argument('--account',
                                    help='Fully qualified name for the '
                                         'account',
                                    required=True)
                parser.add_argument('--asset',
                                    help='Fully qualified name for the asset '
                                         'to store in the holding',
                                    required=True)
                parser.add_argument('--count',
                                    help='Number of instances of the asset '
                                         'stored in the holding',
                                    default=0,
                                    type=int)
                parser.add_argument('--name',
                                    help='Relative name, must begin with /',
                                    default='')
                parser.add_argument('--description',
                                    help='Description of the holding',
                                    default='')
                parser.add_argument('--symbol',
                                    help='Symbol to associate with the newly '
                                         'created id')
                options = parser.parse_args(pargs[1:])

                accountid = self.MarketState.n2i(options.account)
                assetid = self.MarketState.n2i(options.asset)

                txnid = self.MarketClient.register_holding(
                    accountid, assetid, int(options.count), options.name,
                    options.description)
                if txnid and options.symbol:
                    self.IdentityMap[options.symbol] = txnid
                    print "${} = {}".format(options.symbol, txnid)

            elif pargs[0] == 'unr':
                parser.add_argument('--name',
                                    help='Fully qualified name',
                                    required=True)
                options = parser.parse_args(pargs[1:])

                objectid = self.MarketState.n2i(options.name)
                txnid = self.MarketClient.unregister_holding(objectid)

            self._finish(txnid, options.waitforcommit)
            return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_liability(self, args):
        """
        liability -- register or unregister a liability
            liability reg -- register a new liability
            liability unr -- unregister an existing liability
        """
        pargs = shlex.split(self._expandargs(args))

        subcommands = ['reg', 'unr']
        if len(pargs) == 0 or pargs[0] not in subcommands:
            print 'Unknown sub-command, expecting one of {0}'.format(
                subcommands)
            return

        try:
            parser = argparse.ArgumentParser(prog='liability reg|unr')
            parser.add_argument('--waitforcommit',
                                help='Wait for transaction to commit before '
                                     'returning',
                                action='store_true')

            if pargs[0] == 'reg':
                parser.add_argument('--account',
                                    help='Fully qualified name for the '
                                         'account',
                                    required=True)
                parser.add_argument('--type',
                                    help='Fully qualified name for the asset '
                                         'type to store in the liability',
                                    required=True)
                parser.add_argument('--count',
                                    help='Number of instances stored in the '
                                         'liability',
                                    default=0,
                                    type=int)
                parser.add_argument('--guarantor',
                                    help='Fully qualified name of the '
                                         'guarantor participant',
                                    required=True)
                parser.add_argument('--name',
                                    help='Relative name, must begin with /',
                                    default='')
                parser.add_argument('--description',
                                    help='Description of the liability',
                                    default='')
                parser.add_argument('--symbol',
                                    help='Symbol to associate with the newly '
                                         'created id')
                options = parser.parse_args(pargs[1:])

                accountid = self.MarketState.n2i(options.account)
                typeid = self.MarketState.n2i(options.type)
                guarantorid = self.MarketState.n2i(options.guarantor)

                txnid = self.MarketClient.register_liability(
                    accountid, typeid, guarantorid, int(options.count),
                    options.name, options.description)
                if txnid and options.symbol:
                    self.IdentityMap[options.symbol] = txnid
                    print "${} = {}".format(options.symbol, txnid)

            elif pargs[0] == 'unr':
                parser.add_argument(
                    '--name',
                    help='Fully qualified name of liability to unregister',
                    required=True)
                options = parser.parse_args(pargs[1:])

                objectid = self.MarketState.n2i(options.name)
                txnid = self.MarketClient.unregister_liability(objectid)

            self._finish(txnid, options.waitforcommit)
            return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_participant(self, args):
        """
        participant -- register or unregister a participant
            participant reg -- register a new participant
            participant unr -- unregister an existing participant
        """
        pargs = shlex.split(self._expandargs(args))

        subcommands = ['reg', 'unr']
        if len(pargs) == 0 or pargs[0] not in subcommands:
            print 'Unknown sub-command, expecting one of {0}'.format(
                subcommands)
            return

        try:
            parser = argparse.ArgumentParser(prog='participant reg|unr')
            parser.add_argument('--waitforcommit',
                                help='Wait for transaction to commit before '
                                     'returning',
                                action='store_true')

            if pargs[0] == 'reg':
                parser.add_argument('--description',
                                    help='Description of the participant',
                                    default='')
                parser.add_argument('--name',
                                    help='Name of the participant, must not '
                                         'start with "/" Default: ' +
                                    self.MarketClient.LocalNode.Name,
                                    default=self.MarketClient.LocalNode.Name)
                parser.add_argument('--symbol',
                                    help='Symbol to associate with the newly '
                                         'created id')
                options = parser.parse_args(pargs[1:])

                txnid = self.MarketClient.register_participant(
                    options.name, options.description)

                if txnid:
                    self.MarketClient.CreatorID = txnid
                    self.MarketState.CreatorID = txnid
                    self.prompt = self.MarketState.i2n(txnid) + '> '

                    self.IdentityMap['_partid_'] = txnid
                    self.IdentityMap['_name_'] = self.MarketState.i2n(txnid)

                if txnid and options.symbol:
                    self.IdentityMap[options.symbol] = txnid
                    print "${} = {}".format(options.symbol, txnid)

            elif pargs[0] == 'unr':
                parser.add_argument(
                    '--name',
                    help='Fully qualified name of participant to unregister',
                    required=True)
                options = parser.parse_args(pargs[1:])

                objectid = self.MarketState.n2i(options.name)
                txnid = self.MarketClient.unregister_participant(objectid)

                if txnid:
                    self.prompt = '//UNKNOWN> '

            self._finish(txnid, options.waitforcommit)
            return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_selloffer(self, args):
        """
        selloffer -- register or unregister a sell offer
            selloffer reg -- register a new sell offer
            selloffer unr -- unregister an existing sell offer
        """
        pargs = shlex.split(self._expandargs(args))

        subcommands = ['reg', 'unr']
        if len(pargs) == 0 or pargs[0] not in subcommands:
            print 'Unknown sub-command, expecting one of {0}'.format(
                subcommands)
            return

        try:
            parser = argparse.ArgumentParser(prog='selloffer reg|unr')
            parser.add_argument(
                '--waitforcommit',
                help='Wait for transaction to commit before returning',
                action='store_true')

            if pargs[0] == 'reg':
                parser.add_argument('--input',
                                    help='Name of the input liability/holding',
                                    required=True)
                parser.add_argument('--output',
                                    help='Name of the output holding',
                                    required=True)
                parser.add_argument('--ratio',
                                    help='Ratio of input to output instances '
                                         'as src dst',
                                    nargs=2,
                                    type=int,
                                    default=(1, 1))
                parser.add_argument('--name',
                                    help='Name to assign to the new offer',
                                    type=str)
                parser.add_argument('--description',
                                    help='Description of the offer',
                                    type=str)
                parser.add_argument('--modifier',
                                    help='Set additional behaviors on offer '
                                         'execution',
                                    choices=('Any',
                                             'ExecuteOnce',
                                             'ExecuteOncePerParticipant'))
                parser.add_argument('--minimum',
                                    help='Minimum number of assets that can '
                                         'be transferred into the offer',
                                    type=int)
                parser.add_argument('--maximum',
                                    help='Maximum number of assets that can '
                                         'be transferred into the offer',
                                    type=int)
                parser.add_argument('--symbol',
                                    help='Symbol to associate with the '
                                         'newly created id')
                options = parser.parse_args(pargs[1:])

                inputid = self.MarketState.n2i(options.input)
                outputid = self.MarketState.n2i(options.output)

                kwargs = {}
                if options.name:
                    kwargs['name'] = options.name
                if options.description:
                    kwargs['description'] = options.description
                if options.minimum:
                    kwargs['minimum'] = int(options.minimum)
                if options.maximum:
                    kwargs['maximum'] = int(options.maximum)
                if options.modifier:
                    kwargs['execution'] = options.modifier

                ratio = float(options.ratio[1]) / float(options.ratio[0])
                txnid = self.MarketClient.register_selloffer(inputid, outputid,
                                                             ratio, **kwargs)
                if txnid and options.symbol:
                    self.IdentityMap[options.symbol] = txnid
                    print "${} = {}".format(options.symbol, txnid)

            elif pargs[0] == 'unr':
                parser.add_argument('--name',
                                    help='Fully qualified name',
                                    required=True)
                options = parser.parse_args(pargs[1:])

                objectid = self.MarketState.n2i(options.name)
                txnid = self.MarketClient.unregister_selloffer(objectid)

            self._finish(txnid, options.waitforcommit)
            return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_holdings(self, args):
        """
        holdings -- informative list of information about holdings
        """
        pargs = shlex.split(self._expandargs(args))

        try:
            parser = argparse.ArgumentParser(prog='holdings')
            parser.add_argument(
                '--creator',
                help='Filter offers by the name of the creator',
                type=str)
            parser.add_argument('--assets',
                                help='Type of the asset',
                                nargs='+')
            parser.add_argument('--sortby',
                                help='Field to sort on',
                                default='name')
            parser.add_argument('--verbose',
                                help='Verbose listing',
                                action='store_true')
            options = parser.parse_args(pargs)

            filters = [mktplace_state.Filters.holdings()]

            if options.creator:
                creator = self.MarketState.n2i(options.creator)
                filters.append(mktplace_state.Filters.matchvalue('creator',
                                                                 creator))

            if options.assets:
                assetids = [self.MarketState.n2i(n) for n in options.assets]
                filters.append(mktplace_state.Filters.references('asset',
                                                                 assetids))

            holdingids = self.MarketState.lambdafilter(*filters)
            self._dump_holding_list(holdingids,
                                    sortkey=options.sortby,
                                    verbose=options.verbose)
            return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def do_offers(self, args):
        """
        offers == informative list of available offers
        """

        pargs = shlex.split(self._expandargs(args))

        try:
            parser = argparse.ArgumentParser(prog='offers')
            parser.add_argument(
                '--creator',
                help='Filter offers by the name of the creator',
                type=str)
            parser.add_argument(
                '--iasset',
                help='Type of the input asset. (Asset you will pay)',
                type=str)
            parser.add_argument(
                '--oasset',
                help='Type of the output asset. (Asset you will get)',
                type=str)
            parser.add_argument('--sortby',
                                help='Field to sort on',
                                default='name')
            options = parser.parse_args(pargs)

            filters = [mktplace_state.Filters.offers()]

            if options.creator:
                creator = self.MarketState.n2i(options.creator)
                filters.append(mktplace_state.Filters.matchvalue('creator',
                                                                 creator))

            if options.iasset:
                assetid = self.MarketState.n2i(options.iasset)
                bytype = mktplace_state.Filters.matchtype('Holding')
                byasset = mktplace_state.Filters.matchvalue('asset', assetid)
                holdingids = self.MarketState.lambdafilter(bytype, byasset)

                filters.append(mktplace_state.Filters.references('input',
                                                                 holdingids))

            if options.oasset:
                assetid = self.MarketState.n2i(options.oasset)
                bytype = mktplace_state.Filters.matchtype('Holding')
                byasset = mktplace_state.Filters.matchvalue('asset', assetid)
                holdingids = self.MarketState.lambdafilter(bytype, byasset)

                filters.append(mktplace_state.Filters.references('output',
                                                                 holdingids))

            offerids = self.MarketState.lambdafilter(*filters)
            self._dump_offer_list(offerids, sortkey=options.sortby)
            return

        except SystemExit as se:
            if se.code > 0:
                print 'An error occurred processing {0}: {1}'.format(args,
                                                                     str(se))
            return

        except Exception as e:
            print 'An error occurred processing {0}: {1}'.format(args, str(e))
            return

    def _dump_holding_list(self, holdingids, sortkey='name', verbose=False):
        holdings = []
        for holdingid in holdingids:
            holding = self.MarketState.State[holdingid]
            holding['id'] = holdingid
            holdings.append(holding)

        if verbose:
            print "{0:8} {1}".format('Balance', 'Holding')
        for holding in sorted(holdings, key=lambda h: h[sortkey]):
            print "{0:<8} {1}".format(holding['count'],
                                      self.MarketState.i2n(holding['id']))

    def _dump_offer_list(self, offerids, sortkey='name'):
        """
        Utility routine to dump a list of offers
        """
        offers = []
        for offerid in offerids:
            offer = self.MarketState.State[offerid]
            offer['id'] = offerid
            offers.append(offer)

        print "{0:8} {1:35} {2:35} {3}".format(
            'Ratio', 'Input Asset (What You Pay)',
            'Output Asset (What You Get)', 'Name')
        for offer in sorted(offers, key=lambda h: h[sortkey]):
            iholding = self.MarketState.State[offer['input']]
            oholding = self.MarketState.State[offer['output']]
            name = self.MarketState.i2n(offer.get('id'))
            print "{0:<8} {1:35} {2:35} {3}".format(
                offer['ratio'], self.MarketState.i2n(iholding['asset']),
                self.MarketState.i2n(oholding['asset']), name)

    def do_exit(self, args):
        """
        exit -- shutdown the simulator and exit the command loop
        """
        return True

    # pylint: disable=invalid-name
    # EOF handler is expected to be caps to match the symbol Cmd sends
    # when the EOF character is sent.
    def do_EOF(self, args):
        """
        exit -- shutdown the simulator and exit the command loop
        """
        return True


def parse_script_file(filename):
    import re
    cpattern = re.compile('##.*$')

    with open(filename) as fp:
        lines = fp.readlines()

    cmdlines = []
    for line in lines:
        line = re.sub(cpattern, '', line.strip())
        if len(line) > 0:
            cmdlines.append(line)

    return cmdlines


def verify_key(creator, key):
    key_addr = pybitcointools.pubtoaddr(pybitcointools.privtopub(key))
    if key_addr != creator['address']:
        print "Participant signing key mismatch."
        print "The key loaded does not match the key the participant was " \
              "created with."
        return False
    return True


def local_main(config):
    try:
        url = config['LedgerURL']
        signingkey = config['SigningKey']
    except KeyError as ke:
        print 'missing required configuration parameter {0}'.format(ke)
        return

    state = mktplace_state.MarketPlaceState(url)
    state.fetch()

    creator = None
    if 'ParticipantId' in config:
        id = config['ParticipantId']
        creator = state.n2i(id)

        if creator in state.State:
            ptxn = state.State[creator]
        else:
            print "Participant transaction {} not found.".format(id)
            return

        if ptxn['object-type'] != 'Participant':
            print "Id {} is not a participant".format(id)
            return

        if 'ParticipantName' in config:
            print 'Participant Name and Id specified, ignoring name, using ' \
                  'id to find participant.'

        name = ptxn["name"]
        if not name:
            name = id
    else:
        try:
            # None acceptable, as they wont be found
            name = config['ParticipantName']
        except:
            pass
        creator = state.n2i('//' + name)

    if creator:
        if not verify_key(state.State[creator], signingkey):
            return

    state.CreatorID = creator

    client = mktplace_client.MarketPlaceClient(url,
                                               creator=creator,
                                               name=name,
                                               keystring=signingkey,
                                               state=state)

    controller = ClientController(client, echo=config["Echo"])

    varmap = config.get("VariableMap", {})
    for (key, val) in varmap:
        controller.IdentityMap[key] = val

    controller.IdentityMap['_name_'] = name

    script = config.get("ScriptFile", [])
    if script:
        echo = config["Echo"]
        cmdlines = parse_script_file(script)
        for cmdline in cmdlines:
            if echo:
                print cmdline
            if controller.onecmd(cmdline):
                return

    controller.cmdloop()
    print ""


def parse_command_line(args):
    parser = argparse.ArgumentParser()

    parser.add_argument('--config',
                        help='configuration file',
                        default=['mktclient.js'],
                        nargs='+')
    parser.add_argument('--keyfile', help='Name of the key file')
    parser.add_argument('--conf-dir', help='Name of the config directory')
    parser.add_argument('--id',
                        help='The participant id to use, this supersedes the '
                             'participant name.')
    parser.add_argument('--log-config',
                        help='The python logging config file')
    parser.add_argument('--name',
                        help='Name of the participant to use as the creator')
    parser.add_argument('--url', help='Default url for connection')
    parser.add_argument('--script',
                        help='File from which to read script',
                        required=False)
    parser.add_argument('--mapvar', help='Variables', nargs=2, action='append')
    parser.add_argument('--set',
                        help='Specify arbitrary configuration options',
                        nargs=2,
                        action='append')
    parser.add_argument('-e',
                        '--echo',
                        help='echo commands before executing them',
                        required=False,
                        action='store_true',
                        default=False)
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='increase output sent to stderr')

    return parser.parse_args(args)


def get_configuration(args, os_name=os.name, config_files_required=True):
    options = parse_command_line(args)

    options_config = ArgparseOptionsConfig(
        [
            ('keyfile', 'KeyFile'),
            ('conf_dir', 'ConfigDirectory'),
            ('log_dir', 'LogDirectory'),
            ('log_config', 'LogConfigFile'),
            ('url', 'LedgerURL'),
            ('script', 'ScriptName'),
            ('script', 'ScriptFile'),
            ('name', 'ParticipantName'),
            ('id', 'ParticipantId'),
            ('mapvar', 'VariableMap'),
            ('echo', 'Echo'),
            ('verbose', 'Verbose'),
        ], options)

    cfg = get_mktplace_configuration(options.config, options_config, os_name,
                                     config_files_required)

    # General options
    if options.set:
        for (k, v) in options.set:
            cfg[k] = v

    return cfg

globalClog = None


def log_configuration(cfg):
    if 'LogConfigFile' in cfg and len(cfg['LogConfigFile']) > 0:
        log_config_file = cfg['LogConfigFile']
        if log_config_file.split(".")[-1] == "js":
            try:
                with open(log_config_file) as log_config_fd:
                    log_dic = json.load(log_config_fd)
                    logging.config.dictConfig(log_dic)
            except IOError, ex:
                print >>sys.stderr, "Could not read log config: {}" \
                    .format(str(ex))
                sys.exit(1)
        elif log_config_file.split(".")[-1] == "yaml":
            try:
                with open(log_config_file) as log_config_fd:
                    log_dic = yaml.load(log_config_fd)
                    logging.config.dictConfig(log_dic)
            except IOError, ex:
                print >>sys.stderr, "Could not read log config: {}"\
                    .format(str(ex))
                sys.exit(1)

        else:
            print >>sys.stderr, "LogConfigFile type not supported: {}"\
                .format(cfg['LogConfigFile'])
            sys.exit(1)

    else:
        global globalClog
        if not globalClog:
            globalClog = logging.StreamHandler()
            globalClog.setFormatter(logging.Formatter(
                '[%(asctime)s %(name)s %(levelname)s] %(message)s',
                "%H:%M:%S"))
            globalClog.setLevel(logging.WARN)
            logging.getLogger().addHandler(globalClog)


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

    if 'LogLevel' in cfg:
        print >>sys.stderr, "LogLevel is no longer supported, use " \
            "LogConfigFile instead"
        sys.exit(1)

    if 'LogFile' in cfg:
        print >>sys.stderr, "LogFile is no longer supported, use " \
            "LogConfigFile instead"
        sys.exit(1)

    setup_loggers(cfg["Verbose"])
    log_configuration(cfg)

    if "KeyFile" in cfg:
        keyfile = cfg["KeyFile"]
        if os.path.isfile(cfg["KeyFile"]):
            logger.info('read signing key from %s', keyfile)
            key = read_key_file(keyfile)
            cfg['SigningKey'] = key
        else:
            logger.warn('unable to find locate key file %s', keyfile)

    else:
        logger.warn('no key file specified')

    local_main(cfg)


if __name__ == '__main__':
    main(sys.argv[1:])

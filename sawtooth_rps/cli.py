#!/usr/bin/env python
#
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
# -----------------------------------------------------------------------------


import os
import sys
import traceback
import ConfigParser
import getpass
import argparse
import logging
import pybitcointools

from sawtooth_xo.xo_cli import setup_loggers

from .client import RPSClient
from sawtooth_rps.exceptions import RPSException
from sawtooth.exceptions import ClientException


logger = logging.getLogger(__name__)


def do_list(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = RPSClient(base_url=url, keyfile=key_file)
    state = client.get_state()

    print "GAMES:"
    for k, v in state.iteritems():
        creator = v['InitialID']
        players = v.get('Players')
        state = v.get('State')
        print "%s\tplayers: %s status: %s creator: %s" % (k, players, state.capitalize(), creator)
        if state == "COMPLETE":
            print "  Hands Played:"
            for player, hand in v['Hands'].iteritems():
                print "    %s: %s" % (player, hand.capitalize())
            print "  Results:"
            for other_player, result in v['Results'].iteritems():
                print "    %s vs %s: %s" % (creator, other_player, result)
        else:
            print "  Hands Played:"
            for player, hand in v['Hands'].iteritems():
                print "    %s: %s" % (player, "*******")

def do_init(args, config):
    username = config.get('DEFAULT', 'username')
    if args.username is not None:
        username = args.username

    config.set('DEFAULT', 'username', username)
    print "set username: {}".format(username)

    save_config(config)

    wif_filename = config.get('DEFAULT', 'key_file')
    if wif_filename.endswith(".wif"):
        addr_filename = wif_filename[0:-len(".wif")] + ".addr"
    else:
        addr_filename = wif_filename + ".addr"

    if not os.path.exists(wif_filename):
        try:
            if not os.path.exists(os.path.dirname(wif_filename)):
                os.makedirs(os.path.dirname(wif_filename))

            privkey = pybitcointools.random_key()
            encoded = pybitcointools.encode_privkey(privkey, 'wif')
            addr = pybitcointools.privtoaddr(privkey)

            with open(wif_filename, "w") as wif_fd:
                print "writing file: {}".format(wif_filename)
                wif_fd.write(encoded)
                wif_fd.write("\n")

            with open(addr_filename, "w") as addr_fd:
                print "writing file: {}".format(addr_filename)
                addr_fd.write(addr)
                addr_fd.write("\n")
        except IOError, ioe:
            raise RPSException("IOError: {}".format(str(ioe)))


def do_create(args, config):
    name = args.name
    players = args.players

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = RPSClient(base_url=url, keyfile=key_file)
    client.create(name=name, players=players)

    if args.wait:
        client.wait_for_commit()


def do_play(args, config):
    name = args.name
    hand = args.hand.upper()

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = RPSClient(base_url=url, keyfile=key_file)
    client.shoot(name=name, hand=hand)

    if args.wait:
        client.wait_for_commit()


def load_config(config_file=None):
    home = os.path.expanduser("~")
    real_user = getpass.getuser()

    if config_file is None:
        config_file = os.path.join(home, ".sawtooth", "rps.cfg")
    else:
        config_file = os.path.expanduser(config_file)
        if not os.path.isfile(config_file):
            raise RPSException("config file '%s' does not exist" % config_file)

    key_dir = os.path.join(home, ".sawtooth", "keys")

    config = ConfigParser.SafeConfigParser()
    config.set('DEFAULT', 'url', 'http://localhost:8800')
    config.set('DEFAULT', 'key_dir', key_dir)
    config.set('DEFAULT', 'key_file', '%(key_dir)s/%(username)s.wif')
    config.set('DEFAULT', 'username', real_user)
    if os.path.exists(config_file):
        config.read(config_file)

    return config


def save_config(config):
    home = os.path.expanduser("~")

    config_file = os.path.join(home, ".sawtooth", "rps.cfg")
    if not os.path.exists(os.path.dirname(config_file)):
        os.makedirs(os.path.dirname(config_file))

    with open("{}.new".format(config_file), "w") as fd:
        config.write(fd)
    os.rename("{}.new".format(config_file), config_file)


def main():
    parser = argparse.ArgumentParser(prog="rps", add_help=False)
    parser.add_argument('-v', '--verbose', action='count', help='enable more verbose output')
    parser.add_argument('--config', '-c', type=str, help='config file')

    arg_parser = argparse.ArgumentParser(parents=[parser], formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = arg_parser.add_subparsers(title='subcommands', dest='command')
    list_parser = subparsers.add_parser('list', parents=[parser])
    init_parser = subparsers.add_parser('init', parents=[parser])
    init_parser.add_argument('--username', type=str, help='the name of the player')
    create_parser = subparsers.add_parser('create', parents=[parser])
    create_parser.add_argument('name', type=str, help='an identifier for the new game')
    create_parser.add_argument('--wait', action='store_true', default=False, help='wait for this commit before exiting')
    create_parser.add_argument('--players', type=int, default=2, help='number of players in the game')
    play_parser = subparsers.add_parser('play', parents=[parser])
    play_parser.add_argument('name', type=str, help='an identifier for the new game')
    play_parser.add_argument('hand', type=str, help='hand must be either ROCK, PAPER or SCISSORS')
    play_parser.add_argument('--wait', action='store_true', default=False, help='wait for this commit before exiting')

    args = arg_parser.parse_args()
    if args.verbose is None:
        verbose_level = 0
    else:
        verbose_level = args.verbose

    setup_loggers(verbose_level=verbose_level)

    config = load_config(config_file=args.config)

    if args.command == "list":
        do_list(args, config)
    elif args.command == "init":
        do_init(args, config)
    elif args.command == "create":
        do_create(args, config)
    elif args.command == "play":
        do_play(args, config)
    else:
        logger.error("Invalid command")

def main_wrapper():
    try:
        main()
    except RPSException as e:
        print >>sys.stderr, "Error: {}".format(e)
        sys.exit(1)
    except ClientException as e:
        print >>sys.stderr, "Error: {}".format(e)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        raise e
    except:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

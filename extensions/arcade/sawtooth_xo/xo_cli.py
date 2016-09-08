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
# ------------------------------------------------------------------------------


import argparse
import ConfigParser
import getpass
import logging
import os
import traceback
import sys
import pybitcointools

from colorlog import ColoredFormatter

from sawtooth.exceptions import ClientException
from sawtooth.exceptions import InvalidTransactionError

from sawtooth_xo.xo_client import XoClient
from sawtooth_xo.xo_exceptions import XoException


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


def setup_loggers(verbose_level):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(create_console_handler(verbose_level))


def add_create_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('create', parents=[parent_parser])

    parser.add_argument(
        'name',
        type=str,
        help='an identifier for the new game')

    parser.add_argument(
        '--disable-client-validation',
        action='store_true',
        default=False,
        help='disable client validation')

    parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting')


def add_init_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('init', parents=[parent_parser])

    parser.add_argument(
        '--username',
        type=str,
        help='the name of the player')


def add_list_parser(subparsers, parent_parser):
    subparsers.add_parser('list', parents=[parent_parser])


def add_show_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('show', parents=[parent_parser])

    parser.add_argument(
        'name',
        type=str,
        help='the identifier for the game')


def add_take_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('take', parents=[parent_parser])

    parser.add_argument(
        'name',
        type=str,
        help='the identifier for the game')

    parser.add_argument(
        'space',
        type=int,
        help='the square number to take')

    parser.add_argument(
        '--disable-client-validation',
        action='store_true',
        default=False,
        help='disable client validation')

    parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting')


def create_parent_parser(prog_name):
    parent_parser = argparse.ArgumentParser(prog=prog_name, add_help=False)
    parent_parser.add_argument(
        '-v', '--verbose',
        action='count',
        help='enable more verbose output')

    return parent_parser


def create_parser(prog_name):
    parent_parser = create_parent_parser(prog_name)

    parser = argparse.ArgumentParser(
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers(title='subcommands', dest='command')

    add_create_parser(subparsers, parent_parser)
    add_init_parser(subparsers, parent_parser)
    add_list_parser(subparsers, parent_parser)
    add_show_parser(subparsers, parent_parser)
    add_take_parser(subparsers, parent_parser)

    return parser


def do_create(args, config):
    name = args.name

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = XoClient(base_url=url,
                      keyfile=key_file,
                      disable_client_validation=args.disable_client_validation)
    client.create(name=name)

    if args.wait:
        client.wait_for_commit()


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
            raise XoException("IOError: {}".format(str(ioe)))


def do_list(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = XoClient(base_url=url, keyfile=key_file)
    state = client.get_state()

    fmt = "%-15s %-15.15s %-15.15s %-9s %s"
    print fmt % ('GAME', 'PLAYER 1', 'PLAYER 2', 'BOARD', 'STATE')
    for name in state:
        if 'Player1' in state[name]:
            player1 = state[name]['Player1']
        else:
            player1 = ''
        if 'Player2' in state[name]:
            player2 = state[name]['Player2']
        else:
            player2 = ''
        board = state[name]['Board']
        game_state = state[name]['State']
        print fmt % (name, player1, player2, board, game_state)


def do_show(args, config):
    name = args.name

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = XoClient(base_url=url, keyfile=key_file)
    state = client.get_state()

    if name not in state:
        raise XoException('no such game: {}'.format(name))

    game = state[name]

    player1 = ''
    player2 = ''
    if 'Player1' in game:
        player1 = game['Player1']
    if 'Player2' in game:
        player2 = game['Player2']
    board = list(game['Board'].replace('-', ' '))
    game_state = game['State']

    print "GAME:     : {}".format(name)
    print "PLAYER 1  : {}".format(player1)
    print "PLAYER 2  : {}".format(player2)
    print "STATE     : {}".format(game_state)
    print ""
    print "  {} | {} | {}".format(board[0], board[1], board[2])
    print " ---|---|---"
    print "  {} | {} | {}".format(board[3], board[4], board[5])
    print " ---|---|---"
    print "  {} | {} | {}".format(board[6], board[7], board[8])
    print ""


def do_take(args, config):
    name = args.name
    space = args.space

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = XoClient(base_url=url,
                      keyfile=key_file,
                      disable_client_validation=args.disable_client_validation)
    client.take(name=name, space=space)

    if args.wait:
        client.wait_for_commit()


def load_config():
    home = os.path.expanduser("~")
    real_user = getpass.getuser()

    config_file = os.path.join(home, ".sawtooth", "xo.cfg")
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

    config_file = os.path.join(home, ".sawtooth", "xo.cfg")
    if not os.path.exists(os.path.dirname(config_file)):
        os.makedirs(os.path.dirname(config_file))

    with open("{}.new".format(config_file), "w") as fd:
        config.write(fd)
    if os.name == 'nt':
        if os.path.exists(config_file):
            os.remove(config_file)
    os.rename("{}.new".format(config_file), config_file)


def main(prog_name=os.path.basename(sys.argv[0]), args=sys.argv[1:]):
    parser = create_parser(prog_name)
    args = parser.parse_args(args)

    if args.verbose is None:
        verbose_level = 0
    else:
        verbose_level = args.verbose

    setup_loggers(verbose_level=verbose_level)

    config = load_config()

    if args.command == 'create':
        do_create(args, config)
    elif args.command == 'init':
        do_init(args, config)
    elif args.command == 'list':
        do_list(args, config)
    elif args.command == 'show':
        do_show(args, config)
    elif args.command == 'take':
        do_take(args, config)
    else:
        raise XoException("invalid command: {}".format(args.command))


def main_wrapper():
    try:
        main()
    except XoException as e:
        print >>sys.stderr, "Error: {}".format(e)
        sys.exit(1)
    except InvalidTransactionError as e:
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

# Copyright 2017 Intel Corporation
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

from __future__ import print_function

import argparse
import configparser
import getpass
import logging
import os
import traceback
import sys
import shutil
import pkg_resources

from colorlog import ColoredFormatter

import sawtooth_signing.secp256k1_signer as signing

from sawtooth_xo.xo_client import XoClient
from sawtooth_xo.xo_exceptions import XoException


DISTRIBUTION_NAME = 'sawtooth-xo'


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
        nargs='?',
        const=sys.maxsize,
        type=int,
        help='wait for game to commit, set an integer to specify a timeout')


def add_init_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('init', parents=[parent_parser])

    parser.add_argument(
        '--username',
        type=str,
        help='the name of the player')

    parser.add_argument(
        '--url',
        type=str,
        help='the url of the REST API')


def add_reset_parser(subparsers, parent_parser):
    subparsers.add_parser('reset', parents=[parent_parser])


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
        '--wait',
        nargs='?',
        const=sys.maxsize,
        type=int,
        help='wait for take to commit, set an integer to specify a timeout')


def create_parent_parser(prog_name):
    parent_parser = argparse.ArgumentParser(prog=prog_name, add_help=False)
    parent_parser.add_argument(
        '-v', '--verbose',
        action='count',
        help='enable more verbose output')

    try:
        version = pkg_resources.get_distribution(DISTRIBUTION_NAME).version
    except pkg_resources.DistributionNotFound:
        version = 'UNKNOWN'

    parent_parser.add_argument(
        '-V', '--version',
        action='version',
        version=(DISTRIBUTION_NAME + ' (Hyperledger Sawtooth) version {}')
        .format(version),
        help='print version information')

    parent_parser.add_argument(
        '--auth-user',
        type=str,
        help='username for authentication if REST API is using Basic Auth')

    parent_parser.add_argument(
        '--auth-password',
        type=str,
        help='password for authentication if REST API is using Basic Auth')

    return parent_parser


def create_parser(prog_name):
    parent_parser = create_parent_parser(prog_name)

    parser = argparse.ArgumentParser(
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers(title='subcommands', dest='command')

    add_create_parser(subparsers, parent_parser)
    add_init_parser(subparsers, parent_parser)
    add_reset_parser(subparsers, parent_parser)
    add_list_parser(subparsers, parent_parser)
    add_show_parser(subparsers, parent_parser)
    add_take_parser(subparsers, parent_parser)

    return parser


def do_init(args, config):
    username = config.get('DEFAULT', 'username')
    if args.username is not None:
        username = args.username

    url = config.get('DEFAULT', 'url')
    if args.url is not None:
        url = args.url

    config.set('DEFAULT', 'username', username)
    print("set username: {}".format(username))
    config.set('DEFAULT', 'url', url)
    print("set url: {}".format(url))

    save_config(config)

    priv_filename = config.get('DEFAULT', 'key_file')
    if priv_filename.endswith(".priv"):
        addr_filename = priv_filename[0:-len(".priv")] + ".addr"
    else:
        addr_filename = priv_filename + ".addr"

    if not os.path.exists(priv_filename):
        try:
            if not os.path.exists(os.path.dirname(priv_filename)):
                os.makedirs(os.path.dirname(priv_filename))

            privkey = signing.generate_privkey()
            pubkey = signing.generate_pubkey(privkey)
            addr = signing.generate_identifier(pubkey)

            with open(priv_filename, "w") as priv_fd:
                print("writing file: {}".format(priv_filename))
                priv_fd.write(privkey)
                priv_fd.write("\n")

            with open(addr_filename, "w") as addr_fd:
                print("writing file: {}".format(addr_filename))
                addr_fd.write(addr)
                addr_fd.write("\n")
        except IOError as ioe:
            raise XoException("IOError: {}".format(str(ioe)))


def do_reset(args, config):
    home = os.path.expanduser("~")
    config_dir = os.path.join(home, ".sawtooth")

    if os.path.exists(config_dir):
        shutil.rmtree(home, ".sawtooth")


def do_list(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')
    auth_user, auth_password = _get_auth_info(args)

    client = XoClient(base_url=url, keyfile=key_file)

    game_list = [
        game.split(',')
        for games in client.list(auth_user=auth_user,
                                 auth_password=auth_password)
        for game in games.decode().split('|')
    ]

    if game_list is not None:
        fmt = "%-15s %-15.15s %-15.15s %-9s %s"
        print(fmt % ('GAME', 'PLAYER 1', 'PLAYER 2', 'BOARD', 'STATE'))
        for game_data in game_list:

            name, board, game_state, player1, player2 = game_data

            print(fmt % (name, player1[:6], player2[:6], board, game_state))
    else:
        raise XoException("Could not retrieve game listing.")


def do_show(args, config):
    name = args.name

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')
    auth_user, auth_password = _get_auth_info(args)

    client = XoClient(base_url=url, keyfile=key_file)

    data = client.show(name, auth_user=auth_user, auth_password=auth_password)

    if data is not None:

        board_str, game_state, player1, player2 = {
            name: (board, state, player_1, player_2)
            for name, board, state, player_1, player_2 in [
                game.split(',')
                for game in data.decode().split('|')
            ]
        }[name]

        board = list(board_str.replace("-", " "))

        print("GAME:     : {}".format(name))
        print("PLAYER 1  : {}".format(player1[:6]))
        print("PLAYER 2  : {}".format(player2[:6]))
        print("STATE     : {}".format(game_state))
        print("")
        print("  {} | {} | {}".format(board[0], board[1], board[2]))
        print(" ---|---|---")
        print("  {} | {} | {}".format(board[3], board[4], board[5]))
        print(" ---|---|---")
        print("  {} | {} | {}".format(board[6], board[7], board[8]))
        print("")

    else:
        raise XoException("Game not found: {}".format(name))


def do_create(args, config):
    name = args.name

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')
    auth_user, auth_password = _get_auth_info(args)

    client = XoClient(base_url=url, keyfile=key_file)

    if args.wait and args.wait > 0:
        response = client.create(
            name, wait=args.wait,
            auth_user=auth_user,
            auth_password=auth_password)
    else:
        response = client.create(
            name, auth_user=auth_user,
            auth_password=auth_password)

    print("Response: {}".format(response))


def do_take(args, config):
    name = args.name
    space = args.space

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')
    auth_user, auth_password = _get_auth_info(args)

    client = XoClient(base_url=url, keyfile=key_file)

    if args.wait and args.wait > 0:
        response = client.take(
            name, space, wait=args.wait,
            auth_user=auth_user,
            auth_password=auth_password)
    else:
        response = client.take(
            name, space,
            auth_user=auth_user,
            auth_password=auth_password)

    print("Response: {}".format(response))


def load_config():
    home = os.path.expanduser("~")
    real_user = getpass.getuser()

    config_file = os.path.join(home, ".sawtooth", "xo.cfg")
    key_dir = os.path.join(home, ".sawtooth", "keys")

    config = configparser.ConfigParser()
    config.set('DEFAULT', 'url', 'http://127.0.0.1:8080')
    config.set('DEFAULT', 'key_dir', key_dir)
    config.set('DEFAULT', 'key_file', '%(key_dir)s/%(username)s.priv')
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


def _get_auth_info(args):
    auth_user = args.auth_user
    auth_password = args.auth_password
    if auth_user is not None and auth_password is None:
        auth_password = getpass.getpass(prompt="Auth Password: ")

    return auth_user, auth_password


def main(prog_name=os.path.basename(sys.argv[0]), args=None):
    if args is None:
        args = sys.argv[1:]
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
    elif args.command == 'reset':
        do_reset(args, config)
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
    except XoException as err:
        print("Error: {}".format(err), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except SystemExit as err:
        raise err
    except BaseException as err:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

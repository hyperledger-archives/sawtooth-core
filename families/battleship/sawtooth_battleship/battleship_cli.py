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

from __future__ import print_function

import argparse
import configparser
import getpass
import json
import logging
import os
import traceback
import sys

from colorlog import ColoredFormatter

from sawtooth_signing import create_context

from sawtooth_battleship.battleship_board import BoardLayout
from sawtooth_battleship.battleship_board import create_nonces
from sawtooth_battleship.battleship_client import BattleshipClient
from sawtooth_battleship.battleship_exceptions import BattleshipException


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
        '--ships',
        type=str,
        help="a space delimited string of ship types: 'AAA SS BBB'"
    )

    parser.add_argument(
        '--wait',
        nargs='?',
        const=sys.maxsize,
        type=int,
        help='wait for game to commit, set an integer to specify a timeout')


def add_fire_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('fire', parents=[parent_parser])

    parser.add_argument(
        'name',
        type=str,
        help='the identifier for the game')

    parser.add_argument(
        'column',
        type=str,
        help='the column to fire upon (A-J)')

    parser.add_argument(
        'row',
        type=str,
        help='the row to fire upon (1-10)')

    parser.add_argument(
        '--wait',
        nargs='?',
        const=sys.maxsize,
        type=int,
        help='wait for game to commit, set an integer to specify a timeout')


def add_join_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('join', parents=[parent_parser])

    parser.add_argument(
        'name',
        type=str,
        help='the identifier for the game')

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


def add_list_parser(subparsers, parent_parser):
    subparsers.add_parser('list', parents=[parent_parser])


def add_show_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('show', parents=[parent_parser])

    parser.add_argument(
        'name',
        type=str,
        help='the identifier for the game')


def add_genstats_parser(subparsers, parent_parser):
    parser = subparsers.add_parser('genstats', parents=[parent_parser])

    parser.add_argument(
        '--count',
        type=int,
        default=100000,
        help='the number of games to create')

    parser.add_argument(
        '--size',
        type=int,
        default=10,
        help='the board size')


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
    add_fire_parser(subparsers, parent_parser)
    add_genstats_parser(subparsers, parent_parser)
    add_init_parser(subparsers, parent_parser)
    add_join_parser(subparsers, parent_parser)
    add_list_parser(subparsers, parent_parser)
    add_show_parser(subparsers, parent_parser)

    return parser


def do_create(args, config):
    name = args.name
    if args.ships is not None:
        ships = args.ships.split(' ')
    else:
        ships = ["AAAAA", "BBBB", "CCC", "DD", "DD", "SSS", "SSS"]

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = BattleshipClient(base_url=url, keyfile=key_file, wait=args.wait)
    client.create(name=name, ships=ships)


def do_init(args, config):
    username = args.username \
        if args.username else config.get('DEFAULT', 'username')
    url = args.url if args.url else config.get('DEFAULT', 'url')

    config.set('DEFAULT', 'username', username)
    config.set('DEFAULT', 'url', url)

    print("set username: %s" % username)
    print("set url: %s" % url)

    save_config(config)

    priv_filename = config.get('DEFAULT', 'key_file')
    if priv_filename.endswith(".priv"):
        public_key_filename = priv_filename[0:-len(".priv")] + ".pub"
    else:
        public_key_filename = priv_filename + ".pub"

    if not os.path.exists(priv_filename):
        try:
            if not os.path.exists(os.path.dirname(priv_filename)):
                os.makedirs(os.path.dirname(priv_filename))

            context = create_context('secp256k1')
            private_key = context.new_random_private_key()
            public_key = context.get_public_key(private_key)

            with open(priv_filename, "w") as priv_fd:
                print("writing file: {}".format(priv_filename))
                priv_fd.write(private_key.as_hex())
                priv_fd.write("\n")

            with open(public_key_filename, "w") as public_key_fd:
                print("writing file: {}".format(public_key_filename))
                public_key_fd.write(public_key.as_hex())
                public_key_fd.write("\n")
        except IOError as ioe:
            raise BattleshipException("IOError: {}".format(str(ioe)))


def do_fire(args, config):
    name = args.name
    column = args.column
    row = args.row

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    data = load_data(config)

    if name not in data['games']:
        raise BattleshipException(
            "no such game in local database: {}".format(name))

    client = BattleshipClient(base_url=url, keyfile=key_file, wait=args.wait)
    state = client.list_games()

    if name not in state:
        raise BattleshipException(
            "no such game: {}".format(name))
    state_game = state[name]

    reveal_space = None
    reveal_nonce = None

    if 'LastFireColumn' in state_game:
        last_col = ord(state_game['LastFireColumn']) - ord('A')
        last_row = int(state_game['LastFireRow']) - 1

        layout = BoardLayout.deserialize(data['games'][name]['layout'])
        nonces = data['games'][name]['nonces']

        reveal_space = layout.render()[last_row][last_col]
        reveal_nonce = nonces[last_row][last_col]

    response = client.fire(
        name=name,
        column=column,
        row=row,
        reveal_space=reveal_space,
        reveal_nonce=reveal_nonce)

    print(response)


def do_join(args, config):
    name = args.name

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    data = load_data(config)

    client_for_state = BattleshipClient(base_url=url, keyfile=key_file)
    state = client_for_state.list_games()
    if name not in state:
        raise BattleshipException(
            "No such game: {}".format(name)
        )
    game = state[name]
    ships = game['Ships']

    if name not in data['games']:
        new_layout = BoardLayout.generate(ships=ships)
        data['games'][name] = {}
        data['games'][name]['layout'] = new_layout.serialize()
        data['games'][name]['nonces'] = create_nonces(new_layout.size)

        home = os.path.expanduser("~")

        username = config.get('DEFAULT', 'username')

        data_file = os.path.join(home,
                                 ".sawtooth",
                                 "battleship-{}.data".format(username))
        with open(data_file + ".new", 'w') as fd:
            json.dump(data, fd, sort_keys=True, indent=4)
        if os.name == 'nt':
            if os.path.exists(data_file):
                os.remove(data_file)
        os.rename(data_file + ".new", data_file)
    else:
        print("Board and nonces already defined for game, reusing...")

    layout = BoardLayout.deserialize(data['games'][name]['layout'])
    nonces = data['games'][name]['nonces']

    hashed_board = layout.render_hashed(nonces)

    client = BattleshipClient(base_url=url, keyfile=key_file, wait=args.wait)
    client.join(name=name, board=hashed_board)


def do_list(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = BattleshipClient(base_url=url, keyfile=key_file)
    state = client.list_games()

    fmt = "%-15s %-15.15s %-15.15s %s"
    print(fmt % ('GAME', 'PLAYER 1', 'PLAYER 2', 'STATE'))

    keys = list(state.keys())
    keys.sort()
    for name in keys:
        if 'Player1' in state[name]:
            player1 = state[name]['Player1']
        else:
            player1 = ''
        if 'Player2' in state[name]:
            player2 = state[name]['Player2']
        else:
            player2 = ''
        game_state = state[name]['State']
        print(fmt % (name, player1, player2, game_state))


def do_show(args, config):
    name = args.name

    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    data = load_data(config)

    client = BattleshipClient(base_url=url, keyfile=key_file)
    state = client.list_games()

    if name not in state:
        raise BattleshipException('no such game: {}'.format(name))

    game = state[name]

    player1 = ''
    player2 = ''
    if 'Player1' in game:
        player1 = game['Player1']
    if 'Player2' in game:
        player2 = game['Player2']
    game_state = game['State']

    print("GAME:     : {}".format(name))
    print("PLAYER 1  : {}".format(player1))
    print("PLAYER 2  : {}".format(player2))
    print("STATE     : {}".format(game_state))

    # figure out the proper user's target board, given the public_key
    priv_filename = config.get('DEFAULT', 'key_file')
    if priv_filename.endswith(".priv"):
        public_key_filename = priv_filename[0:-len(".priv")] + ".pub"
    else:
        public_key_filename = priv_filename + ".pub"
    public_key_file = open(public_key_filename, mode='r')
    public_key = public_key_file.readline().rstrip('\n')

    if 'Player1' in game and public_key == game['Player1']:
        target_board_name = 'TargetBoard1'
    elif 'Player2' in game and public_key == game['Player2']:
        target_board_name = 'TargetBoard2'
    else:
        raise BattleshipException("Player hasn't joined game.")

    # figure out who fired last and who is calling do_show
    # to determine which board * is diplayed on to
    # show pending shot
    if 'LastFireRow' in game and 'LastFireColumn' in game:
        last_fire = (int(game['LastFireRow']) - 1,
                     int(ord(game['LastFireColumn'])) - ord('A'))
    else:
        last_fire = None

    if game_state == 'P1-NEXT' and target_board_name == 'TargetBoard1':
        # player 2 last shot and player 1 is looking
        will_be_on_target_board = False
    elif game_state == 'P1-NEXT' and target_board_name == 'TargetBoard2':
        # player 2 last shot and player 2 is looking
        will_be_on_target_board = True
    elif game_state == 'P2-NEXT' and target_board_name == 'TargetBoard1':
        # player 1 last shot and player 1 is looking
        will_be_on_target_board = True
    elif game_state == 'P2-NEXT' and target_board_name == 'TargetBoard2':
        # player 1 last shot and player 2 is looking
        will_be_on_target_board = False
    else:
        last_fire = None
        will_be_on_target_board = False

    if target_board_name in game:
        target_board = game[target_board_name]
        size = len(target_board)

        print()
        print("  Target Board")
        print_board(target_board, size, is_target_board=True,
                    pending_on_target_board=will_be_on_target_board,
                    last_fire=last_fire)

    if name in data['games']:
        layout = BoardLayout.deserialize(data['games'][name]['layout'])
        board = layout.render()
        size = len(board)

        print()
        print("  Secret Board")
        print_board(board, size, is_target_board=False,
                    pending_on_target_board=will_be_on_target_board,
                    last_fire=last_fire)


def print_board(board, size, is_target_board=True,
                pending_on_target_board=False, last_fire=None):
    print(''.join(["-"] * (size * 3 + 3)))
    print("  ", end=' ')
    for i in range(0, size):
        print(" {}".format(chr(ord('A') + i)), end=' ')
    print()

    for row_idx, row in enumerate(range(0, size)):
        print("%2d" % (row + 1), end=' ')
        for col_idx, space in enumerate(board[row]):
            if is_target_board:
                if pending_on_target_board and last_fire is not None and \
                        row_idx == last_fire[0] and col_idx == last_fire[1]:

                    print(" {}".format(
                        space.replace('?', '*')
                    ), end=' ')
                else:
                    print(" {}".format(
                        space.replace('?', ' ')
                        .replace('M', '.').replace('H', 'X')
                    ), end=' ')

            else:
                if not pending_on_target_board and last_fire is not None and \
                        row_idx == last_fire[0] and col_idx == last_fire[1]:
                    print(" {}".format(
                        '*'
                    ), end=' ')
                else:
                    print(" {}".format(
                        space.replace('-', ' ')
                    ), end=' ')
        print()


def do_genstats(args, config):
    count = args.count
    size = args.size
    ships = ["AAAAA", "BBBB", "CCC", "DD", "DD", "SSS", "SSS"]
    # Create a board which contains a count of the number of time
    # a space was used.
    count_board = [[0] * size for i in range(size)]
    for i in range(0, count):
        layout = BoardLayout.generate(size=size, ships=ships)
        board = layout.render()
        for row in range(0, size):
            for col in range(0, size):
                if board[row][col] != '-':
                    count_board[row][col] += 1

    print("Percentages Board")
    print("-----------------")

    # Print the board of percentages.
    print("  ", end=' ')
    for i in range(0, size):
        print("  {}".format(chr(ord('A') + i)), end=' ')
    print()

    for row in range(0, size):
        print("%2d" % (row + 1), end=' ')
        for space in count_board[row]:
            print("%3.0f" % (float(space) / float(count) * 100,), end=' ')
        print()

    print()
    print("Total Games Created: {}".format(count))


def load_config():
    home = os.path.expanduser("~")
    real_user = getpass.getuser()

    config_file = os.path.join(home, ".sawtooth", "battleship.cfg")
    key_dir = os.path.join(home, ".sawtooth", "keys")

    config = configparser.SafeConfigParser()
    config.set('DEFAULT', 'url', 'http://127.0.0.1:8008')
    config.set('DEFAULT', 'key_dir', key_dir)
    config.set('DEFAULT', 'key_file', '%(key_dir)s/%(username)s.priv')
    config.set('DEFAULT', 'username', real_user)
    if os.path.exists(config_file):
        config.read(config_file)

    return config


def save_config(config):
    home = os.path.expanduser("~")

    config_file = os.path.join(home, ".sawtooth", "battleship.cfg")
    if not os.path.exists(os.path.dirname(config_file)):
        os.makedirs(os.path.dirname(config_file))

    with open("{}.new".format(config_file), "w") as fd:
        config.write(fd)
    if os.name == 'nt':
        if os.path.exists(config_file):
            os.remove(config_file)
    os.rename("{}.new".format(config_file), config_file)


def load_data(config):
    home = os.path.expanduser("~")

    username = config.get('DEFAULT', 'username')

    data_file = os.path.join(home,
                             ".sawtooth",
                             "battleship-{}.data".format(username))
    if os.path.exists(data_file):
        with open(data_file, 'r') as fd:
            data = json.load(fd)
    else:
        data = {'games': {}}

    return data


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
    elif args.command == 'fire':
        do_fire(args, config)
    elif args.command == 'genstats':
        do_genstats(args, config)
    elif args.command == 'init':
        do_init(args, config)
    elif args.command == 'join':
        do_join(args, config)
    elif args.command == 'list':
        do_list(args, config)
    elif args.command == 'show':
        do_show(args, config)
    else:
        raise BattleshipException("invalid command: {}".format(args.command))


def main_wrapper():
    try:
        main()
    except BattleshipException as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        raise e
    except BaseException:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

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
import json
import logging
import os
import traceback
import sys

from colorlog import ColoredFormatter

from sawtooth.exceptions import ClientException
from sawtooth.exceptions import InvalidTransactionError

from sawtooth_bond.btp_cli_funcs import do_bond_list, do_bond_show
from sawtooth_bond.btp_cli_funcs import do_holding_create, do_holding_list
from sawtooth_bond.btp_cli_funcs import do_holding_show, do_order_create
from sawtooth_bond.btp_cli_funcs import do_order_list, do_order_show
from sawtooth_bond.btp_cli_funcs import do_org_create, do_org_list
from sawtooth_bond.btp_cli_funcs import do_org_show, do_user_list
from sawtooth_bond.btp_cli_funcs import do_user_register, do_user_show
from sawtooth_bond.btp_cli_funcs import do_quote_create, do_quote_list
from sawtooth_bond.btp_cli_funcs import do_quote_show, do_settlement_create
from sawtooth_bond.btp_cli_funcs import do_settlement_list, do_settlement_show
from sawtooth_bond.btp_cli_funcs import do_user_update, do_receipt_list
from sawtooth_bond.btp_cli_funcs import do_receipt_show, do_order, do_receipt
from sawtooth_bond.btp_cli_funcs import do_user, do_holding, do_settlement
from sawtooth_bond.btp_cli_funcs import do_bond, do_init
from sawtooth_bond.btp_cli_funcs import do_load, do_org, do_quote

from sawtooth_bond.btp_cli_utils import load_config


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


def add_init_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'init',
        parents=[parent_parser],
        help='configure the cli client',
        epilog="""Example:
        btp init --username johndoe --url http://192.168.5.1:8800
        """
    )

    parser.add_argument(
        '--username',
        type=str,
        help='the name of the user')
    parser.add_argument(
        '--url',
        type=str,
        help='the url of the validator to connect with'
    )


def add_load_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'load',
        parents=[parent_parser],
        help='load a YAML file',
        epilog="""Example:
        btp load data.yml
        """
    )

    parser.add_argument(
        'filename',
        type=str,
        nargs='+',
        help='filename of YAML file to load')

    parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting')


def add_bond_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'bond',
        parents=[parent_parser],
        help='list and show bonds'
    )
    bond_subparsers = parser.add_subparsers(title='bond subcommands')
    list_parser = bond_subparsers.add_parser(
        'list',
        parents=[parent_parser],
        help='list all the bonds'
    )
    list_parser.set_defaults(func=do_bond_list)
    list_parser.add_argument(
        '--yaml',
        action='store_true',
        help='display the list of bonds in YAML format'
    )

    list_parser.add_argument(
        '--full',
        action='store_true',
        help='show columns wider than 30 characters')
    show_parser = bond_subparsers.add_parser(
        'show',
        parents=[parent_parser],
        help="show a particular bond"
    )
    show_parser.add_argument(
        'identifier',
        type=str,
        help='object id, isin, or cusip'
    )
    show_parser.set_defaults(func=do_bond_show)


def add_org_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'org',
        parents=[parent_parser],
        help='list, show, and create organizations'
    )
    org_subparsers = parser.add_subparsers(title='org subcommands')
    c_parser = org_subparsers.add_parser(
        'create',
        help='create an organization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:
    btp org create --ticker CMP10 --industry Technology 'Company 10'""",
        parents=[parent_parser]
    )
    c_parser.add_argument(
        'name',
        type=str,
        help='the name of the organization. e.g. "Company 10"'
    )
    c_parser.add_argument(
        '--object-id',
        type=str,
        help="specify the object-id for the organization"
    )
    c_parser.add_argument(
        '--ticker',
        type=str,
        help="the ticker symbol of the organization"
    )
    c_parser.add_argument(
        '--pricing-src',
        type=str,
        help="a four letter code for marketmakers"
    )
    c_parser.add_argument(
        '--industry',
        type=str,
        help="the organization's industry"
    )
    c_parser.add_argument(
        '--auth',
        type=json.loads,
        help='who in the organization is authorized to '
             'act as marketmaker or trader as an array '
             'of json objects '
             'e.g. \'[{"Role": "marketmaker", '
             '"ParticipantId": "OBJECT_ID"}]\'')
    c_parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting')
    c_parser.set_defaults(func=do_org_create)
    list_parser = org_subparsers.add_parser(
        'list',
        parents=[parent_parser],
        help='list all organizations'
    )
    list_parser.add_argument(
        '--yaml',
        action='store_true',
        help='display the list in YAML format'
    )
    list_parser.add_argument(
        '--full',
        action='store_true',
        help='list columns wider than 30 characters'
    )
    list_parser.set_defaults(func=do_org_list)
    show_parser = org_subparsers.add_parser(
        'show',
        parents=[parent_parser],
        help="show a particular organization"
    )
    show_parser.add_argument(
        'identifier',
        type=str,
        help="object-id, ticker, or pricing-source (only applies to "
             "marketmakers"
    )
    show_parser.set_defaults(func=do_org_show)


def add_quote_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'quote',
        parents=[parent_parser],
        help='list, show, and create quotes'
    )

    quote_subparsers = parser.add_subparsers(title='quote subcommands')
    c_parser = quote_subparsers.add_parser(
        'create',
        help='create a quote',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:
btp quote create --cusip 22160KAF2 CMP2 '101-13+' 100000 '99-12 1/8' 100000""",
        parents=[parent_parser]
    )
    c_parser.add_argument(
        'firm',
        type=str,
        help='the pricing-source of the firm making the quote'
    )
    c_parser.add_argument(
        'ask-price',
        type=str,
        help='the ask price')
    c_parser.add_argument(
        'ask-qty',
        type=int,
        help='the ask quantity')
    c_parser.add_argument(
        'bid-price',
        type=str,
        help='the bid price')
    c_parser.add_argument(
        'bid-qty',
        type=int,
        help='The bid quantity')
    c_parser.add_argument(
        '--isin',
        type=str,
        help='the isin of the bond')
    c_parser.add_argument(
        '--cusip',
        type=str,
        help='The cusip of the bond, (either '
             '--cusip or --isin must be specified)')
    c_parser.add_argument(
        '--object-id',
        type=str,
        help="optionally specify the created quote's object-id")
    c_parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting')
    c_parser.set_defaults(func=do_quote_create)
    list_parser = quote_subparsers.add_parser(
        'list',
        parents=[parent_parser],
        help='list all quotes, or filter by --org or --user'
    )
    list_parser.add_argument(
        '--org',
        type=str,
        help='The org object-id, ticker, or pricing-source '
             '(only applies to marketmakers'
    )
    list_parser.add_argument(
        '--user',
        type=str,
        help='The username, object-id, or key-id of the user'
    )
    list_parser.add_argument(
        '--yaml',
        action='store_true',
        help='display the quote info in YAML'
    )
    list_parser.add_argument(
        '--full',
        action='store_true',
        help='display columns that are wider than 30 characters'
    )
    list_parser.set_defaults(func=do_quote_list)
    show_parser = quote_subparsers.add_parser(
        'show',
        parents=[parent_parser],
        help="show a particular quote"
    )
    show_parser.add_argument(
        'identifier',
        type=str,
        help='The object-id of the quote'
    )
    show_parser.set_defaults(func=do_quote_show)


def add_holding_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'holding',
        parents=[parent_parser],
        help='list, show, and create holdings'
    )

    holding_subparsers = parser.add_subparsers(title='holding subcommands')
    c_parser = holding_subparsers.add_parser(
        'create',
        help="create a holding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:
                    btp holding create CMP3 Currency USD 1000000000
                    btp holding create CMP1 Bond US2847D48509 100000""",
        parents=[parent_parser],
    )
    c_parser.add_argument(
        'owner',
        type=str,
        help='the object-id, ticker, or pricing-source of the organization'
    )
    c_parser.add_argument(
        'asset-type',
        type=str,
        help='either Currency or Bond'
    )
    c_parser.add_argument(
        'asset-id',
        type=str,
        help="The bond identifier(isin, cusip, object-id) or if Currency "
             "the string USD"
    )
    c_parser.add_argument(
        'amount',
        type=float,
        help="The amount of the holding"
    )
    c_parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting'
    )
    c_parser.add_argument(
        '--object-id',
        type=str,
        help="optionally specify the created holding's object-id"
    )
    c_parser.set_defaults(func=do_holding_create)
    list_parser = holding_subparsers.add_parser(
        'list',
        parents=[parent_parser],
        help='list all holdings, or just those specified with --org'
    )
    list_parser.add_argument(
        '--org',
        type=str,
        help='the org object-id, ticker, or pricing-source '
             '(only applies to marketmakers'
    )
    list_parser.add_argument(
        '--yaml',
        action='store_true',
        help='Display the holding info in YAML'
    )
    list_parser.add_argument(
        '--full',
        action='store_true',
        help='display columns that are wider than 30 characters'
    )
    list_parser.set_defaults(func=do_holding_list)
    show_parser = holding_subparsers.add_parser(
        'show',
        parents=[parent_parser],
        help='show a particular holding'
    )
    show_parser.add_argument(
        'identifier',
        type=str,
        help='the object id of the holding'
    )
    show_parser.set_defaults(func=do_holding_show)


def add_settlement_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'settlement',
        parents=[parent_parser],
        help='list, show, and create settlements'
    )

    settlement_subparsers = parser.add_subparsers(
        title='settlement subcommands'
    )

    c_parser = settlement_subparsers.add_parser(
        'create',
        help='create a settlement',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:
                    btp settlement create OBJECT_ID""",
        parents=[parent_parser]
    )
    c_parser.add_argument(
        'order-id',
        type=str,
        help='the object-id of the order for settlement'
    )
    c_parser.add_argument(
        '--object-id',
        type=str,
        help="optionally specify the created settlement's object-id"
    )
    c_parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting')
    c_parser.set_defaults(func=do_settlement_create)
    list_parser = settlement_subparsers.add_parser(
        'list',
        parents=[parent_parser],
        help='list all settlements, filter by --creator (key-id, '
             'username, or object-id of the creator of the settlement)'
    )
    list_parser.add_argument(
        '--creator',
        type=str,
        help='the key-id, username, or object-id'
    )
    list_parser.add_argument(
        '--full',
        action='store_true',
        default=False,
        help='display columns that are wider than 30 characters'
    )
    list_parser.add_argument(
        '--yaml',
        action='store_true',
        default=False,
        help='display as settlement as YAML'
    )
    list_parser.set_defaults(func=do_settlement_list)
    show_parser = settlement_subparsers.add_parser(
        'show',
        parents=[parent_parser],
        help="show a particular settlement"
    )
    show_parser.add_argument(
        'object-id',
        help='The object-id of the settlement or the object-id of the order'
    )
    show_parser.set_defaults(func=do_settlement_show)


def add_user_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'user',
        parents=[parent_parser],
        help='list, show, register, and update users'
    )
    user_subparsers = parser.add_subparsers(title='User subcommands')
    register_parser = user_subparsers.add_parser(
        'register',
        help='register the current user',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:
                    btp user init --username johndoe
                    btp user register""",
        parents=[parent_parser]
    )
    register_parser.add_argument(
        '--firm-id',
        type=str,
        help="the object-id of the organization"
    )
    register_parser.add_argument(
        '--object-id',
        type=str,
        help="specify the object-id of the created user"
    )
    register_parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting')
    register_parser.set_defaults(func=do_user_register)
    update_parser = user_subparsers.add_parser(
        'update',
        parents=[parent_parser],
        help='update the username and/or firm-id'
    )
    update_parser.add_argument(
        '--username',
        type=str,
        help="the username to change the user to, ("
             "must be unique)"
    )
    update_parser.add_argument(
        '--firm-id',
        type=str,
        help="the firm-id to add or change for the user"
    )
    update_parser.add_argument(
        'object-id',
        type=str,
        help="the object-id of the user to update"
    )
    update_parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting'
    )
    update_parser.set_defaults(func=do_user_update)

    list_parser = user_subparsers.add_parser(
        'list',
        parents=[parent_parser],
        help='list all users'
    )
    list_parser.add_argument(
        '--yaml',
        action='store_true',
        help='display the holding info in YAML'
    )
    list_parser.add_argument(
        '--full',
        action='store_true',
        help='display columns wider than 30 characters'
    )
    list_parser.set_defaults(func=do_user_list)
    show_parser = user_subparsers.add_parser(
        'show',
        parents=[parent_parser],
        help="show a particular user"
    )
    show_parser.add_argument(
        'identifier',
        type=str,
        help='the username, object-id, or key-id of the user'
    )
    show_parser.set_defaults(func=do_user_show)


def add_order_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'order',
        parents=[parent_parser],
        help='list, show, and create orders'
    )

    order_subparsers = parser.add_subparsers(title='order subcommands')
    c_parser = order_subparsers.add_parser(
        'create',
        help="create an order",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:
btp order create --isin US035242AP13 Buy Market 100000 --firm-id OBJECT_ID""",
        parents=[parent_parser],
    )
    c_parser.add_argument(
        'action',
        type=str,
        help='Buy or Sell'
    )
    c_parser.add_argument(
        'order-type',
        type=str,
        help='Limit or Market'
    )
    c_parser.add_argument(
        'quantity',
        type=int,
        help='the amount of bonds being sold or bought e.g. 1000000'
    )
    c_parser.add_argument(
        '--firm-id',
        type=str,
        help="the organization's object-id"
    )
    c_parser.add_argument(
        '--isin',
        type=str,
        help="the isin of the bond the order is on"
    )
    c_parser.add_argument(
        '--cusip',
        type=str,
        help="the cusip of the bond the order is on "
             "(one of --cusip or --isin is required)"
    )
    c_parser.add_argument(
        '--limit-price',
        type=str,
        help='the limit-price to buy or sell at e.g. "101-15 1/4"'
    )
    c_parser.add_argument(
        '--limit-yield',
        type=float,
        help="the limit-yield to buy or sell at e.g. 1.248"
    )
    c_parser.add_argument(
        '--object-id',
        type=str,
        help="specify an object-id for the order"
    )
    c_parser.add_argument(
        '--wait',
        action='store_true',
        default=False,
        help='wait for this commit before exiting'
    )
    c_parser.set_defaults(func=do_order_create)
    list_parser = order_subparsers.add_parser(
        'list',
        parents=[parent_parser],
        help='list all orders limited by --user or --org'
    )
    list_parser.add_argument(
        '--yaml',
        action='store_true'
    )
    list_parser.add_argument(
        '--full',
        action='store_true',
        help='display columns wider than 30 characters'
    )
    identifier_parser = list_parser.\
        add_mutually_exclusive_group(required=False)
    identifier_parser.add_argument(
        '--user',
        type=str,
        help='the object-id, key-id, or username of user'
    )
    identifier_parser.add_argument(
        '--org',
        type=str,
        help='the object-id, ticker, or pricing-source '
             '(only applies to marketmakers)'
    )
    list_parser.set_defaults(func=do_order_list)

    show_subparser = order_subparsers.add_parser(
        'show',
        parents=[parent_parser],
        help='show a particular order, including settlement if applicable'
    )
    show_subparser.add_argument(
        'identifier',
        type=str,
        help='the object-id of the order'
    )
    show_subparser.set_defaults(func=do_order_show)


def add_receipt_parser(subparsers, parent_parser):
    parser = subparsers.add_parser(
        'receipt',
        parents=[parent_parser],
        help='list and show receipts'
    )
    receipt_parser = parser.add_subparsers(title='receipt subcommands')
    list_parser = receipt_parser.add_parser(
        'list',
        parents=[parent_parser],
        help='list redemptions and coupons, filter by --org (payee) or --bond'
    )
    filter_parser = list_parser.add_mutually_exclusive_group(required=False)
    filter_parser.add_argument(
        '--bond',
        help="the isin, cusip, or bond object-id"
    )
    filter_parser.add_argument(
        '--org',
        help='the ticker, pricing-source, or organization object-id'
    )
    list_parser.add_argument(
        '--yaml',
        action='store_true',
        help='display in YAML format'
    )
    list_parser.add_argument(
        '--full',
        action='store_true',
        help='Display columns wider than 30 characters'
    )
    list_parser.set_defaults(func=do_receipt_list)
    show_parser = receipt_parser.add_parser(
        'show',
        parents=[parent_parser],
        help='show a particular redemption or coupon'
    )
    show_parser.add_argument(
        'identifier',
        type=str,
        help='the object-id of the receipt'
    )
    show_parser.set_defaults(func=do_receipt_show)


def create_parent_parser(prog_name):
    parent_parser = argparse.ArgumentParser(prog=prog_name, add_help=False)
    parent_parser.add_argument(
        '-v', '--verbose',
        action='count',
        help="add more v's for more information e.g. -vv"
    )

    return parent_parser


def create_parser(prog_name):
    parent_parser = create_parent_parser(prog_name)

    parser = argparse.ArgumentParser(
        parents=[parent_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    subparsers = parser.add_subparsers(title='subcommands', dest='command')

    add_init_parser(subparsers, parent_parser)
    add_load_parser(subparsers, parent_parser)
    add_bond_parser(subparsers, parent_parser)
    add_org_parser(subparsers, parent_parser)
    add_holding_parser(subparsers, parent_parser)
    add_user_parser(subparsers, parent_parser)
    add_order_parser(subparsers, parent_parser)
    add_quote_parser(subparsers, parent_parser)
    add_settlement_parser(subparsers, parent_parser)
    add_receipt_parser(subparsers, parent_parser)

    return parser


def main(prog_name=os.path.basename(sys.argv[0]), args=sys.argv[1:]):
    parser = create_parser(prog_name)
    args = parser.parse_args(args)

    if args.verbose is None:
        verbose_level = 0
    else:
        verbose_level = args.verbose

    setup_loggers(verbose_level=verbose_level)

    config = load_config()

    if args.command == 'init':
        do_init(args, config)
    elif args.command == 'load':
        do_load(args, config)
    elif args.command == 'bond':
        do_bond(args, config)
    elif args.command == 'org':
        do_org(args, config)
    elif args.command == 'holding':
        do_holding(args, config)
    elif args.command == 'user':
        do_user(args, config)
    elif args.command == 'order':
        do_order(args, config)
    elif args.command == 'quote':
        do_quote(args, config)
    elif args.command == 'settlement':
        do_settlement(args, config)
    elif args.command == 'receipt':
        do_receipt(args, config)
    else:
        raise ClientException("invalid command: {}".format(args.command))


def main_wrapper():
    # pylint: disable=bare-except
    try:
        main()
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

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
import os
import sys
import argparse
import pkg_resources

import psycopg2

from sawtooth_supplychain.subscriber.config import SubscriberConfig
from sawtooth_supplychain.subscriber.config import load_subscriber_config
from sawtooth_supplychain.subscriber.init import do_init
from sawtooth_supplychain.subscriber.subscriber import Subscriber

from sawtooth_sdk.client.log import init_console_logging
from sawtooth_sdk.client.log import log_configuration
from sawtooth_sdk.client.config import get_log_config
from sawtooth_sdk.client.config import get_log_dir
from sawtooth_sdk.messaging.stream import Stream


DISTRIBUTION_NAME = 'sawtooth-supplychain-sds'


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

    return parent_parser


def create_parser(prog_name):
    parent_parser = create_parent_parser(prog_name)

    parser = argparse.ArgumentParser(
        parents=[parent_parser],
        formatter_class=argparse.RawTextHelpFormatter)

    subparsers = parser.add_subparsers(title='subcommands', dest='command')
    subparsers.required = True

    database_parser = argparse.ArgumentParser(add_help=False)

    database_parser.add_argument(
        '--database-name',
        help='The name of the database')

    database_parser.add_argument(
        '--database-host',
        help='The host of the database')

    database_parser.add_argument(
        '--database-port',
        type=int,
        help='The port of the database')

    database_parser.add_argument(
        '--database-user',
        help='The authorized user of the database')

    database_parser.add_argument(
        '--database-password',
        help="The authorized user's password for database access")

    subs_parser = subparsers.add_parser(
        'subscribe',
        parents=[database_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    subs_parser.add_argument(
        '-C', '--connect',
        nargs='?',
        default='tcp://localhost:4004',
        help='Endpoint for the validator connection')

    subparsers.add_parser(
        'init',
        parents=[database_parser],
        formatter_class=argparse.RawDescriptionHelpFormatter)

    return parser


def do_subscribe(opts):
    opts_config = SubscriberConfig(
        connect=opts.connect,
        database_name=opts.database_name,
        database_host=opts.database_host,
        database_port=opts.database_port,
        database_user=opts.database_user,
        database_password=opts.database_password)
    subscriber_config = load_subscriber_config(opts_config)

    subscriber = None
    stream = None
    connection = None
    # pylint: disable=broad-except
    try:

        url = None
        if "tcp://" not in subscriber_config.connect:
            url = "tcp://" + subscriber_config.connect
        else:
            url = subscriber_config.connect

        stream = Stream(url)
        connection = psycopg2.connect(
            dbname=subscriber_config.database_name,
            host=subscriber_config.database_host,
            port=subscriber_config.database_port,
            user=subscriber_config.database_user,
            password=subscriber_config.database_password)
        subscriber = Subscriber(stream, connection)

        log_config = get_log_config(
            filename="supplychain_sds_log_config.toml")
        if log_config is not None:
            log_configuration(log_config=log_config)
        else:
            log_dir = get_log_dir()
            # use the stream zmq identity for filename
            log_configuration(
                log_dir=log_dir,
                name="supplychain-sds-" + str(stream.zmq_id)[2:-1])

        subscriber.start()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print('Error: {}'.format(e), file=sys.stderr)
    finally:
        if subscriber is not None:
            subscriber.shutdown()
        if stream is not None:
            stream.close()
        if connection is not None:
            connection.close()


def main(prog_name=os.path.basename(sys.argv[0]), args=None):
    if args is None:
        args = sys.argv[1:]

    parser = create_parser(prog_name)
    opts = parser.parse_args(args)

    init_console_logging(verbose_level=opts.verbose)

    if opts.command == 'subscribe':
        do_subscribe(opts)
    elif opts.command == 'init':
        do_init(opts)
    else:
        print('Error: Invalid command "{}"'.format(opts.command))

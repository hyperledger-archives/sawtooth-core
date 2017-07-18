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

import psycopg2

from sawtooth_supplychain.subscriber.subscriber import Subscriber
from sawtooth_supplychain.subscriber.config import SubscriberConfig
from sawtooth_supplychain.subscriber.config import \
    load_default_subscriber_config
from sawtooth_supplychain.subscriber.config import \
    load_toml_subscriber_config
from sawtooth_supplychain.subscriber.config import \
    merge_subscriber_configs

from sawtooth_sdk.client.log import init_console_logging
from sawtooth_sdk.client.log import log_configuration
from sawtooth_sdk.client.config import get_log_config
from sawtooth_sdk.client.config import get_log_dir
from sawtooth_sdk.client.config import get_config_dir
from sawtooth_sdk.messaging.stream import Stream


def parse_args(args):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-C', '--connect',
                        nargs='?',
                        default='tcp://localhost:4004',
                        help='Endpoint for the validator connection')

    parser.add_argument('-D', '--database',
                        help='Database connection string')

    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='Increase output sent to stderr')

    return parser.parse_args(args)


def load_subscriber_config(first_config):
    default_config = load_default_subscriber_config()
    config_dir = get_config_dir()
    conf_file = os.path.join(config_dir, 'supplychain_sds.toml')

    toml_config = load_toml_subscriber_config(conf_file)
    return merge_subscriber_configs(
        configs=[first_config, toml_config, default_config])


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    subscriber = None
    stream = None
    connection = None
    # pylint: disable=broad-except
    try:
        opts = parse_args(args)
        opts_config = SubscriberConfig(
            connect=opts.connect,
            database=opts.database)

        subscriber_config = load_subscriber_config(opts_config)
        url = None
        if "tcp://" not in subscriber_config.connect:
            url = "tcp://" + subscriber_config.connect
        else:
            url = subscriber_config.connect

        stream = Stream(url)
        connection = psycopg2.connect(subscriber_config.database)
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

        init_console_logging(verbose_level=opts.verbose)

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

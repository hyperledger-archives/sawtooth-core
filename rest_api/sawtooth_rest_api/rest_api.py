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

import os
import sys
import logging
import asyncio
import argparse
from urllib.parse import urlparse
import platform
import pkg_resources
from aiohttp import web

from zmq.asyncio import ZMQEventLoop
from pyformance import MetricsRegistry
from pyformance.reporters import InfluxReporter

from sawtooth_sdk.processor.log import init_console_logging
from sawtooth_sdk.processor.log import log_configuration
from sawtooth_sdk.processor.config import get_log_config
from sawtooth_sdk.processor.config import get_log_dir
from sawtooth_sdk.processor.config import get_config_dir
from sawtooth_rest_api.messaging import Connection
from sawtooth_rest_api.route_handlers import RouteHandler
from sawtooth_rest_api.state_delta_subscription_handler \
    import StateDeltaSubscriberHandler
from sawtooth_rest_api.config import load_default_rest_api_config
from sawtooth_rest_api.config import load_toml_rest_api_config
from sawtooth_rest_api.config import merge_rest_api_config
from sawtooth_rest_api.config import RestApiConfig


LOGGER = logging.getLogger(__name__)
DISTRIBUTION_NAME = 'sawtooth-rest-api'


def parse_args(args):
    """Parse command line flags added to `rest_api` command.
    """
    parser = argparse.ArgumentParser(
        description='Starts the REST API application and connects to a '
        'specified validator.')

    parser.add_argument('-B', '--bind',
                        help='identify host and port for API to run on \
                        default: http://localhost:8008)',
                        action='append')
    parser.add_argument('-C', '--connect',
                        help='specify URL to connect to a running validator')
    parser.add_argument('-t', '--timeout',
                        help='set time (in seconds) to wait for validator \
                        response')
    parser.add_argument('--client-max-size',
                        type=int,
                        help='the max size (in bytes) of a request body')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='enable more verbose output to stderr')
    parser.add_argument('--opentsdb-url',
                        help='specify host and port for Open TSDB database \
                        used for metrics')
    parser.add_argument('--opentsdb-db',
                        help='specify name of database for storing metrics')

    try:
        version = pkg_resources.get_distribution(DISTRIBUTION_NAME).version
    except pkg_resources.DistributionNotFound:
        version = 'UNKNOWN'

    parser.add_argument(
        '-V', '--version',
        action='version',
        version=(DISTRIBUTION_NAME + ' (Hyperledger Sawtooth) version {}')
        .format(version),
        help='display version information')

    return parser.parse_args(args)


def start_rest_api(host, port, connection, timeout, registry,
                   client_max_size=None):
    """Builds the web app, adds route handlers, and finally starts the app.
    """
    loop = asyncio.get_event_loop()
    connection.open()
    app = web.Application(loop=loop, client_max_size=client_max_size)
    app.on_cleanup.append(lambda app: connection.close())

    # Add routes to the web app
    LOGGER.info('Creating handlers for validator at %s', connection.url)

    handler = RouteHandler(loop, connection, timeout, registry)

    app.router.add_post('/batches', handler.submit_batches)
    app.router.add_get('/batch_statuses', handler.list_statuses)
    app.router.add_post('/batch_statuses', handler.list_statuses)

    app.router.add_get('/state', handler.list_state)
    app.router.add_get('/state/{address}', handler.fetch_state)

    app.router.add_get('/blocks', handler.list_blocks)
    app.router.add_get('/blocks/{block_id}', handler.fetch_block)

    app.router.add_get('/batches', handler.list_batches)
    app.router.add_get('/batches/{batch_id}', handler.fetch_batch)

    app.router.add_get('/transactions', handler.list_transactions)
    app.router.add_get(
        '/transactions/{transaction_id}',
        handler.fetch_transaction)

    app.router.add_get('/receipts', handler.list_receipts)
    app.router.add_post('/receipts', handler.list_receipts)

    app.router.add_get('/peers', handler.fetch_peers)
    app.router.add_get('/status', handler.fetch_status)

    subscriber_handler = StateDeltaSubscriberHandler(connection)
    app.router.add_get('/subscriptions', subscriber_handler.subscriptions)
    app.on_shutdown.append(lambda app: subscriber_handler.on_shutdown())

    # Start app
    LOGGER.info('Starting REST API on %s:%s', host, port)

    web.run_app(
        app,
        host=host,
        port=port,
        access_log=LOGGER,
        access_log_format='%r: %s status, %b size, in %Tf s')


def load_rest_api_config(first_config):
    default_config = load_default_rest_api_config()
    config_dir = get_config_dir()
    conf_file = os.path.join(config_dir, 'rest_api.toml')

    toml_config = load_toml_rest_api_config(conf_file)
    return merge_rest_api_config(
        configs=[first_config, toml_config, default_config])


class MetricsRegistryWrapper():
    def __init__(self, registry):
        self._registry = registry

    def gauge(self, name):
        return self._registry.gauge(
            ''.join([name, ',host=', platform.node()]))

    def counter(self, name):
        return self._registry.counter(
            ''.join([name, ',host=', platform.node()]))

    def timer(self, name):
        return self._registry.timer(
            ''.join([name, ',host=', platform.node()]))


def main():
    loop = ZMQEventLoop()
    asyncio.set_event_loop(loop)

    connection = None
    try:
        opts = parse_args(sys.argv[1:])
        opts_config = RestApiConfig(
            bind=opts.bind,
            connect=opts.connect,
            timeout=opts.timeout,
            opentsdb_url=opts.opentsdb_url,
            opentsdb_db=opts.opentsdb_db,
            client_max_size=opts.client_max_size)
        rest_api_config = load_rest_api_config(opts_config)
        url = None
        if "tcp://" not in rest_api_config.connect:
            url = "tcp://" + rest_api_config.connect
        else:
            url = rest_api_config.connect

        connection = Connection(url)

        log_config = get_log_config(filename="rest_api_log_config.toml")

        # If no toml, try loading yaml
        if log_config is None:
            log_config = get_log_config(filename="rest_api_log_config.yaml")

        if log_config is not None:
            log_configuration(log_config=log_config)
        else:
            log_dir = get_log_dir()
            log_configuration(log_dir=log_dir, name="rest_api")
        init_console_logging(verbose_level=opts.verbose)

        try:
            host, port = rest_api_config.bind[0].split(":")
            port = int(port)
        except ValueError as e:
            print("Unable to parse binding {}: Must be in the format"
                  " host:port".format(rest_api_config.bind[0]))
            sys.exit(1)

        wrapped_registry = None
        if rest_api_config.opentsdb_url:
            LOGGER.info("Adding metrics reporter: url=%s, db=%s",
                        rest_api_config.opentsdb_url,
                        rest_api_config.opentsdb_db)

            url = urlparse(rest_api_config.opentsdb_url)
            proto, db_server, db_port, = url.scheme, url.hostname, url.port

            registry = MetricsRegistry()
            wrapped_registry = MetricsRegistryWrapper(registry)

            reporter = InfluxReporter(
                registry=registry,
                reporting_interval=10,
                database=rest_api_config.opentsdb_db,
                prefix="sawtooth_rest_api",
                port=db_port,
                protocol=proto,
                server=db_server,
                username=rest_api_config.opentsdb_username,
                password=rest_api_config.opentsdb_password)
            reporter.start()

        start_rest_api(
            host,
            port,
            connection,
            int(rest_api_config.timeout),
            wrapped_registry,
            client_max_size=rest_api_config.client_max_size)
        # pylint: disable=broad-except
    except Exception as e:
        LOGGER.exception(e)
        sys.exit(1)
    finally:
        if connection is not None:
            connection.close()

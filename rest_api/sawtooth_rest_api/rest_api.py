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
from aiohttp import web

from zmq.asyncio import ZMQEventLoop

from sawtooth_sdk.client.log import init_console_logging
from sawtooth_sdk.client.log import log_configuration
from sawtooth_sdk.client.config import get_log_config
from sawtooth_sdk.client.config import get_log_dir
from sawtooth_sdk.client.config import get_config_dir
from sawtooth_rest_api.messaging import Connection
from sawtooth_rest_api.route_handlers import RouteHandler
from sawtooth_rest_api.state_delta_subscription_handler \
    import StateDeltaSubscriberHandler
from sawtooth_rest_api.config import load_default_rest_api_config
from sawtooth_rest_api.config import load_toml_rest_api_config
from sawtooth_rest_api.config import merge_rest_api_config
from sawtooth_rest_api.config import RestApiConfig


LOGGER = logging.getLogger(__name__)


def parse_args(args):
    """Parse command line flags added to `rest_api` command.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-B', '--bind',
                        help='The host and port for the api to run on.',
                        action='append')
    parser.add_argument('-C', '--connect',
                        help='The url to connect to a running Validator')
    parser.add_argument('-t', '--timeout',
                        help='Seconds to wait for a validator response')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='Increase level of output sent to stderr')

    return parser.parse_args(args)


async def cors_handler(request):
    headers = {}
    RouteHandler.add_cors_headers(request, headers)
    return web.Response(headers=headers)


def start_rest_api(host, port, connection, timeout):
    """Builds the web app, adds route handlers, and finally starts the app.
    """
    loop = asyncio.get_event_loop()
    connection.open()
    app = web.Application(loop=loop)
    app.on_cleanup.append(lambda app: connection.close())

    # Add routes to the web app
    LOGGER.info('Creating handlers for validator at %s', connection.url)
    handler = RouteHandler(loop, connection, timeout)

    app.router.add_route('OPTIONS', '/{route_name}', cors_handler)

    app.router.add_post('/batches', handler.submit_batches)
    app.router.add_get('/batch_status', handler.list_statuses)
    app.router.add_post('/batch_status', handler.list_statuses)

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

    subscriber_handler = StateDeltaSubscriberHandler(connection)
    app.router.add_get('/subscriptions', subscriber_handler.subscriptions)
    app.on_shutdown.append(lambda app: subscriber_handler.on_shutdown())

    # Start app
    LOGGER.info('Starting REST API on %s:%s', host, port)

    web.run_app(app, host=host, port=port,
                access_log=LOGGER,
                access_log_format='%r: %s status, %b size, in %Tf s')


def load_rest_api_config(first_config):
    default_config = load_default_rest_api_config()
    config_dir = get_config_dir()
    conf_file = os.path.join(config_dir, 'rest_api.toml')

    toml_config = load_toml_rest_api_config(conf_file)
    return merge_rest_api_config(
        configs=[first_config, toml_config, default_config])


def main():
    loop = ZMQEventLoop()
    asyncio.set_event_loop(loop)

    connection = None
    try:
        opts = parse_args(sys.argv[1:])
        opts_config = RestApiConfig(
            bind=opts.bind,
            connect=opts.connect,
            timeout=opts.timeout)
        rest_api_config = load_rest_api_config(opts_config)
        url = None
        if "tcp://" not in rest_api_config.connect:
            url = "tcp://" + rest_api_config.connect
        else:
            url = rest_api_config.connect

        connection = Connection(url)

        log_config = get_log_config(filename="rest_api_log_config.toml")
        if log_config is not None:
            log_configuration(log_config=log_config)
        else:
            log_dir = get_log_dir()
            log_configuration(log_dir=log_dir, name="sawtooth_rest_api")
        init_console_logging(verbose_level=opts.verbose)

        try:
            host, port = rest_api_config.bind[0].split(":")
            port = int(port)
        except ValueError as e:
            print("Unable to parse binding {}: Must be in the format"
                  " host:port".format(rest_api_config.bind[0]))
            sys.exit(1)

        start_rest_api(
            host,
            port,
            connection,
            int(rest_api_config.timeout))
        # pylint: disable=broad-except
    except Exception as e:
        print("Error: {}".format(e), file=sys.stderr)
    finally:
        if connection is not None:
            connection.close()

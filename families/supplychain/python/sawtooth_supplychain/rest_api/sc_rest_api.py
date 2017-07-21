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

# Supply Chain REST API, based on REST API

import os
import sys
import logging
import asyncio
import argparse
from aiohttp import web
from zmq.asyncio import ZMQEventLoop

from sawtooth_sdk.client.config import get_config_dir
from sawtooth_sdk.client.log import init_console_logging
from sawtooth_sdk.client.log import log_configuration
from sawtooth_sdk.client.config import get_log_config
from sawtooth_sdk.client.config import get_log_dir
from sawtooth_supplychain.rest_api.config import load_default_rest_api_config
from sawtooth_supplychain.rest_api.config import load_toml_rest_api_config
from sawtooth_supplychain.rest_api.config import merge_rest_api_config
from sawtooth_supplychain.rest_api.config import RestApiConfig
from sawtooth_supplychain.rest_api.route_handlers import RouteHandler


LOGGER = logging.getLogger(__name__)


def parse_args(args):
    """Parse command line flags added to `rest_api` command.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-B', '--bind',
                        help='The host and port for the api to run on.',
                        action='append')
    parser.add_argument('-v', '--verbose',
                        action='count',
                        default=0,
                        help='Increase level of output sent to stderr')
    parser.add_argument('-D', '--db_cnx',
                        action='store',
                        required=True,
                        help='The database connection string')

    return parser.parse_args(args)


async def cors_handler(request):
    headers = {}
    RouteHandler.add_cors_headers(request, headers)
    return web.Response(headers=headers)


def start_rest_api(host, port, db_cnx):
    """Builds the web app, adds route handlers, and finally starts the app.
    """
    loop = asyncio.get_event_loop()
    app = web.Application(loop=loop)

    # Add routes to the web app
    LOGGER.info('Creating handlers for db queries at %s', db_cnx)

    handler = RouteHandler(loop, db_cnx)

    app.router.add_route('OPTIONS', '/{route_name}', cors_handler)

    app.router.add_get('/agents', handler.list_agents)
    app.router.add_get('/agents/{agent_id}', handler.fetch_agent)
    app.router.add_get('/applications', handler.list_applications)
    app.router.add_get('/records', handler.list_records)
    app.router.add_get('/records/{record_id}', handler.fetch_record)
    app.router.add_get('/records/{record_id}/applications',
                       handler.fetch_applications)

    # Start app
    LOGGER.info('Starting Supplychain REST API on "%s:%s', host, port)
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

    try:
        opts = parse_args(sys.argv[1:])
        opts_config = RestApiConfig(
            bind=opts.bind,
            db_cnx=opts.db_cnx)
        rest_api_config = load_rest_api_config(opts_config)
        # Adding parameters for db connection
        db_cnx = opts.db_cnx

        log_config = get_log_config(filename="supply_chain_rest_api_log_config.toml")
        if log_config is not None:
            log_configuration(log_config=log_config)
        else:
            log_dir = get_log_dir()
            log_configuration(log_dir=log_dir, name="supply_chain_rest_api")
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
            db_cnx)
        # pylint: disable=broad-except
    except Exception as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)

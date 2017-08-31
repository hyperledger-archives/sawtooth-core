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
import pkg_resources

from aiohttp import web

from sawtooth_sdk.client.log import init_console_logging
from sawtooth_sdk.client.log import log_configuration
from sawtooth_sdk.client.config import get_log_config
from sawtooth_sdk.client.config import get_log_dir

from sawtooth_supplychain.rest_api.config import load_rest_api_config
from sawtooth_supplychain.rest_api.config import RestApiConfig
from sawtooth_supplychain.rest_api.route_handlers import RouteHandler


DISTRIBUTION_NAME = 'sawtooth-supplychain-rest-api'
LOGGER = logging.getLogger(__name__)


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
    """Parse command line flags added to `rest_api` command.
    """
    parent_parser = create_parent_parser(prog_name)

    parser = argparse.ArgumentParser(
        parents=[parent_parser],
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        '-B', '--bind',
        help='The host and port for the api to run on.',
        action='append')

    parser.add_argument(
        '--database-name',
        help='The name of the database')

    parser.add_argument(
        '--database-host',
        help='The host of the database')

    parser.add_argument(
        '--database-port',
        type=int,
        help='The port of the database')

    parser.add_argument(
        '--database-user',
        help='The authorized user of the database')

    parser.add_argument(
        '--database-password',
        help="The authorized user's password for database access")

    return parser


def get_host_and_port(rest_api_config):
    try:
        host, port = rest_api_config.bind[0].split(":")
        port = int(port)
        return (host, port)
    except ValueError:
        print("Unable to parse binding {}: Must be in the format"
              " host:port".format(rest_api_config.bind[0]))
        sys.exit(1)


async def cors_handler(request):
    headers = {}
    RouteHandler.add_cors_headers(request, headers)
    return web.Response(headers=headers)


def start_rest_api(rest_api_config):
    """Builds the web app, adds route handlers, and finally starts the app.
    """
    loop = asyncio.get_event_loop()
    app = web.Application(loop=loop)

    # Add routes to the web app
    LOGGER.info('Creating handlers for db queries at %s:%s/%s',
                rest_api_config.database_host, rest_api_config.database_port,
                rest_api_config.database_name)

    handler = RouteHandler(loop, rest_api_config)

    app.router.add_route('OPTIONS', '/{route_name}', cors_handler)

    app.router.add_get('/agents', handler.list_agents)
    app.router.add_get('/agents/{agent_id}', handler.fetch_agent)
    app.router.add_get('/applications', handler.list_applications)
    app.router.add_get('/records', handler.list_records)
    app.router.add_get('/records/{record_id}', handler.fetch_record)
    app.router.add_get('/records/{record_id}/applications',
                       handler.fetch_record_applications)

    # Start app
    host, port = get_host_and_port(rest_api_config)
    LOGGER.info('Starting Supplychain REST API on "%s:%s', host, port)
    web.run_app(app, host=host, port=port,
                access_log=LOGGER,
                access_log_format='%r: %s status, %b size, in %Tf s')


def do_start(opts):
    try:
        opts_config = RestApiConfig(
            bind=opts.bind,
            database_name=opts.database_name,
            database_host=opts.database_host,
            database_port=opts.database_port,
            database_user=opts.database_user,
            database_password=opts.database_password)
        rest_api_config = load_rest_api_config(opts_config)

        log_config = get_log_config(
            filename="supply_chain_rest_api_log_config.toml")
        if log_config is not None:
            log_configuration(log_config=log_config)
        else:
            log_dir = get_log_dir()
            log_configuration(log_dir=log_dir, name="supply_chain_rest_api")

        start_rest_api(rest_api_config)
        # pylint: disable=broad-except
    except Exception as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)


def main(prog_name=os.path.basename(sys.argv[0]), args=None):
    if args is None:
        args = sys.argv[1:]

    parser = create_parser(prog_name)
    opts = parser.parse_args(args)

    init_console_logging(verbose_level=opts.verbose)

    do_start(opts)

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

# Supply Chain REST API, based on REST API

import os
import sys
import time
import logging
import asyncio
import argparse
from aiohttp import web

from sawtooth_sdk.client.config import get_config_dir
from sawtooth_sdk.messaging.stream import Stream

from sawtooth_sdk.client.log import init_console_logging
from sawtooth_sdk.client.log import log_configuration
from sawtooth_sdk.client.config import get_log_config
from sawtooth_sdk.client.config import get_log_dir

from rest_api.config import load_default_rest_api_config
from rest_api.config import load_toml_rest_api_config
from rest_api.config import merge_rest_api_config
from rest_api.config import RestApiConfig
from rest_api.route_handlers import RouteHandler

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


async def access_logger(app, handler):
    """Simple logging middleware to report info about each request/response.
    """
    async def logging_handler(request):
        start_time = time.time()
        request_name = hex(int(start_time * 10000))[-6:]
        client_ip, _ = request.transport.get_extra_info(
            'peername', ('UNKNOWN', None))

        # log request
        LOGGER.info(
            'Request  %s: "%s %s" from %s',
            request_name,
            request.method,
            request.rel_url,
            client_ip)

        def log_response(response):
            # pylint: disable=protected-access
            content_length = response._headers.get('Content-Length',
                                                   'UNKNOWN')
            if content_length == 'UNKNOWN':
                LOGGER.info(
                    'Response %s: %s status, %s size, in %.3fs',
                    request_name,
                    response._status,
                    content_length,
                    time.time() - start_time)
            else:
                LOGGER.info(
                    'Response %s: %s status, %sB size, in %.3fs',
                    request_name,
                    response._status,
                    content_length,
                    time.time() - start_time)

        try:
            response = await handler(request)
            log_response(response)
            return response
        except web.HTTPError as e:
            log_response(e)
            raise e

    return logging_handler


async def cors_handler(request):
    headers = {}
    RouteHandler.add_cors_headers(request, headers)
    return web.Response(headers=headers)


def start_rest_api(host, port, stream, timeout):
    """Builds the web app, adds route handlers, and finally starts the app.
    """
    loop = asyncio.get_event_loop()
    app = web.Application(loop=loop, middlewares=[access_logger])

    # Add routes to the web app
    LOGGER.info('Creating handlers for validator at %s', stream.url)
    handler = RouteHandler(loop, stream, timeout)

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
    web.run_app(app, host=host, port=port, access_log=None)


# Config stuff
def load_rest_api_config(first_config):
    default_config = load_default_rest_api_config()
    config_dir = get_config_dir()
    conf_file = os.path.join(config_dir, 'rest_api.toml')

    toml_config = load_toml_rest_api_config(conf_file)
    return merge_rest_api_config(
        configs=[first_config, toml_config, default_config])


def main():
    stream = None
    try:
        opts = parse_args(sys.argv[1:])
        opts_config = RestApiConfig(
            bind=opts.bind,
            connect=opts.connect,
            timeout=opts.timeout)
        rest_api_config = load_rest_api_config(opts_config)
        if "tcp://" not in rest_api_config.connect:
            stream = Stream("tcp://" + rest_api_config.connect)
        else:
            stream = Stream(rest_api_config.connect)
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
            stream,
            int(rest_api_config.timeout))
        # pylint: disable=broad-except
    except Exception as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
    finally:
        if stream is not None:
            stream.close()

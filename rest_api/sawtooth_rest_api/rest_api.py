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

import sys
import time
import logging
import asyncio
import argparse
from aiohttp import web

from sawtooth_sdk.messaging.stream import Stream
from sawtooth_sdk.client.log import init_console_logging
from sawtooth_sdk.client.log import log_configuration
from sawtooth_sdk.client.config import get_log_config
from sawtooth_sdk.client.config import get_log_dir
from sawtooth_rest_api.route_handlers import RouteHandler


LOGGER = logging.getLogger(__name__)


def parse_args(args):
    """Parse command line flags added to `rest_api` command.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',
                        help='The port for the api to run on',
                        default=8080)
    parser.add_argument('--host',
                        help='The host for the api to run on',
                        default="127.0.0.1")
    parser.add_argument('--stream-url',
                        help='The url to connect to a running Validator',
                        default='tcp://localhost:40000')
    parser.add_argument('--timeout',
                        help='Seconds to wait for a validator response',
                        default=300)
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


def start_rest_api(host, port, stream, timeout):
    """Builds the web app, adds route handlers, and finally starts the app.
    """
    loop = asyncio.get_event_loop()
    app = web.Application(loop=loop, middlewares=[access_logger])

    # Add routes to the web app
    LOGGER.info('Creating handlers for validator at %s', stream.url)
    handler = RouteHandler(loop, stream, timeout)

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

    # Start app
    LOGGER.info('Starting REST API on %s:%s', host, port)
    web.run_app(app, host=host, port=port, access_log=None)


def main():
    stream = None
    try:
        opts = parse_args(sys.argv[1:])
        stream = Stream(opts.stream_url)

        log_config = get_log_config(filename="rest_api_log_config.toml")
        if log_config is not None:
            log_configuration(log_config=log_config)
        else:
            log_dir = get_log_dir()
            log_configuration(log_dir=log_dir, name="sawtooth_rest_api")
        init_console_logging(verbose_level=opts.verbose)

        start_rest_api(
            opts.host,
            int(opts.port),
            stream,
            int(opts.timeout))
        # pylint: disable=broad-except
    except Exception as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)
    finally:
        if stream is not None:
            stream.close()

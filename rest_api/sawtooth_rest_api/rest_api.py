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
import sys
from aiohttp import web
from sawtooth_rest_api.routes import RouteHandler


def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--port',
                        help='The port for the api to run on',
                        default=8080)
    parser.add_argument('--host',
                        help='The host for the api to run on',
                        default="0.0.0.0")
    parser.add_argument('--stream-url',
                        help='The url to connect to a running Validator',
                        default='tcp://localhost:40000')
    parser.add_argument('--timeout',
                        help='Seconds to wait for a validator response',
                        default=300)

    return parser.parse_args(args)


async def logging_middleware(app, handler):
    async def logging_handler(request):
        print('Handling {} request for {}'.format(
            request.method,
            request.rel_url
        ))
        return await handler(request)
    return logging_handler


def start_rest_api(host, port, stream_url, timeout):
    handler = RouteHandler(stream_url, timeout)

    app = web.Application(middlewares=[logging_middleware])
    # Add routes to the web app
    app.router.add_post('/batches', handler.batches_post)

    app.router.add_get('/state', handler.state_list)
    app.router.add_get('/state/{address}', handler.state_get)

    app.router.add_get('/blocks', handler.block_list)
    app.router.add_get('/blocks/{block_id}', handler.block_get)

    web.run_app(app, host=host, port=port)


def main():
    try:
        opts = parse_args(sys.argv[1:])
        start_rest_api(
            opts.host,
            int(opts.port),
            opts.stream_url,
            int(opts.timeout))
        # pylint: disable=broad-except
    except Exception as e:
        print("Error: {}".format(e), file=sys.stderr)
        sys.exit(1)

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

"""
IAS Proxy Server.
"""

import sys
import os
import json
import logging
import traceback

from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler

import requests
import toml

from sawtooth_ias_client import ias_client
from sawtooth_ias_proxy.utils import LruCache
from sawtooth_sdk.processor import config


LOGGER = logging.getLogger(__name__)


class Handler(BaseHTTPRequestHandler):
    client = None
    sig_rl_cache = LruCache(5)
    attestation_cache = LruCache(200)

    def _read_json_request(self):
        data_string = self.rfile.read(
            int(self.headers['Content-Length']))
        return json.loads(data_string.decode('utf-8'))

    def _respond(self, code, data=None, headers=None):
        self.send_response(code)
        if data is not None:
            # Let the caller put in any headers it wants
            if headers is not None:
                for name, value in headers.items():
                    self.send_header(name, value)

            if isinstance(data, dict):
                self.send_header('Content-type', 'application/json')
                content = json.dumps(data).encode('utf-8')
            else:
                self.send_header('Content-type', 'text/plain')
                content = data.encode('utf-8')

            self.send_header('Content-length', len(content))
            self.end_headers()
            self.wfile.write(content)
            return

        self.end_headers()

    def _get_sig_rl(self):
        try:
            cache = self.sig_rl_cache[self.path]
            if cache is None:
                response = \
                    self.client.get_signature_revocation_lists(
                        '',
                        self.path)
                self.sig_rl_cache[self.path] = \
                    {'code': 200, 'response': response}
            else:
                response = cache['response']
        except requests.HTTPError as e:
            self.send_response(e.response.status_code)
            return
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        content = response.encode('utf-8')
        self.send_header('Content-length', len(content))
        self.end_headers()
        self.wfile.write(content)

    def _post_verify_attestation(self):
        json_data = self._read_json_request()
        quote = json_data['isvEnclaveQuote']
        if not quote:
            self._respond(code=404)
            return
        try:
            response = self.attestation_cache[quote]
            if response is None:
                response = \
                    self.client.post_verify_attestation(
                        quote=quote,
                        manifest=json_data.get('pseManifest'),
                        nonce=json_data.get('nonce'))
                if response:
                    self.attestation_cache[quote] = response
        except requests.HTTPError as e:
            self._respond(e.response.status_code,
                          e.response.text.decode('ascii', 'ignore'))
            return
        if not response:
            self._respond(code=520)
        else:
            # The IAS client responds with a dictionary that contains:
            # 'verification_report' and 'signature'.
            # 'verification_report' was pulled from the body
            # of the response from the IAS web service.
            # 'signature' was pulled from the header of the
            # response it got from the IAS web service.
            # We need to re-create the IAS web service response
            headers = None
            signature = response.get('signature')
            if signature is not None:
                headers = {'x-iasreport-signature': signature}
            self._respond(
                code=requests.codes.ok,
                data=response.get('verification_report'),
                headers=headers)

    def do_GET(self):
        # pylint: disable=invalid-name
        if self.path.find('/attestation/sgx/v2/sigrl') == 0:
            self._get_sig_rl()
        else:
            self._respond(404)

    def do_POST(self):
        # pylint: disable=invalid-name
        if self.path.find('/attestation/sgx/v2/report') == 0:
            self._post_verify_attestation()
        else:
            self._respond(404)


class IasProxyServer(object):
    """
    IAS Proxy Server.
    """

    def __init__(self, proxy_config):
        self.httpd = None
        try:
            self._ias_proxy_name = proxy_config['proxy_name']
            self._ias_proxy_port = proxy_config['proxy_port']
        except (AssertionError, KeyError) as e:
            LOGGER.critical('Missing config: %s', e)
            sys.exit(1)
        self.client = \
            ias_client.IasClient(
                ias_url=proxy_config['ias_url'],
                spid_cert_file=proxy_config['spid_cert_file'])

    def stop(self):
        """
        Do an orderly shutdown of the IAS Proxy server.
        @return: None
        """
        self.httpd.shutdown()

    def run(self):
        """
        Start server running, blocks until the process is killed
        or stop is called
        """
        Handler.client = self.client
        self.httpd = \
            HTTPServer(
                (self._ias_proxy_name, self._ias_proxy_port),
                Handler)
        self.httpd.serve_forever()


def get_server():
    config_file = os.path.join(config.get_config_dir(), 'ias_proxy.toml')
    LOGGER.info('Loading IAS Proxy config from: %s', config_file)

    # Lack of a config file is a fatal error, so let the exception percolate
    # up to caller
    with open(config_file) as fd:
        proxy_config = toml.loads(fd.read())

    # Verify the integrity (as best we can) of the TOML configuration file
    valid_keys = set(['proxy_name', 'proxy_port', 'ias_url', 'spid_cert_file'])
    found_keys = set(proxy_config.keys())

    invalid_keys = found_keys.difference(valid_keys)
    if invalid_keys:
        raise \
            ValueError(
                'IAS Proxy config file contains the following invalid '
                'keys: {}'.format(
                    ', '.join(sorted(list(invalid_keys)))))

    missing_keys = valid_keys.difference(found_keys)
    if missing_keys:
        raise \
            ValueError(
                'IAS Proxy config file missing the following keys: '
                '{}'.format(
                    ', '.join(sorted(list(missing_keys)))))

    return IasProxyServer(proxy_config)


def main():
    relay = get_server()
    relay.run()


if __name__ == '__main__':
    # pylint: disable=bare-except
    try:
        main()
    except KeyboardInterrupt:
        pass
    except SystemExit as e:
        raise e
    except:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

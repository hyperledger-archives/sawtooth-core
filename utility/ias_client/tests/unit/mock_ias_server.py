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
Mock IAS server for testing IAS client
"""

import http.server
import threading
import time
import queue


def create(endpoint):
    mis = MockIasServer(endpoint)
    handlers = {
        "up": MockIasStateUp,
        "error": MockIasStateError,
        "slow": MockIasStateSlow,
        "down": MockIasStateDown,
    }
    for state, handler in handlers.items():
        mis.add_state(state, handler)

    return mis


class TestHTTPServer(http.server.HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.requests = queue.Queue()


class MockIasServer:
    """
    Use the State pattern to mock different statuses of the IAS server for
    testing.
    """

    def __init__(self, endpoint):
        if endpoint[:len("http://")] != "http://":
            raise ValueError("Invalid endpoint: " + endpoint)
        host, port = endpoint[len("http://"):].split(":")

        self._address = (host, int(port))
        self._handlers = {}
        self._server = None
        self._thread = None
        self._requests = []

    def start(self, state):
        handler = self._handlers[state]
        self._server = TestHTTPServer(self._address, handler)
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()

    def restart(self, state):
        self.stop()
        self.start(state)

    def add_state(self, state, handler):
        self._handlers[state] = handler

    def get_received(self):
        return self._server.requests.get()


class MockIasStateUp(http.server.BaseHTTPRequestHandler):
    # pylint: disable=invalid-name
    def do_GET(self):
        self.server.requests.put({
            "path": self.path,
            "command": self.command,
            "headers": self.headers,
        })
        self.send_response(200)
        self.end_headers()
        self.request.sendall(b"thisisasignaturelist")

    # pylint: disable=invalid-name
    def do_POST(self):
        self.server.requests.put({
            "path": self.path,
            "command": self.command,
            "headers": self.headers,
            "data": self.rfile.read(int(self.headers.get("content-length"))),
        })
        self.send_response(200)
        self.send_header("x-iasreport-signature", "signature")
        self.end_headers()
        self.request.sendall(b'{"thisisa":"verification_report"}')


class MockIasStateError(http.server.BaseHTTPRequestHandler):
    # pylint: disable=invalid-name
    def do_GET(self):
        self.send_error(503, message="FUBAR")

    # pylint: disable=invalid-name
    def do_POST(self):
        self.send_error(503, message="FUBAR")


class MockIasStateSlow(http.server.BaseHTTPRequestHandler):
    # pylint: disable=invalid-name
    def do_GET(self):
        time.sleep(1)

    # pylint: disable=invalid-name
    def do_POST(self):
        time.sleep(1)


class MockIasStateDown(http.server.BaseHTTPRequestHandler):
    # pylint: disable=invalid-name
    def do_GET(self):
        pass

    # pylint: disable=invalid-name
    def do_POST(self):
        pass

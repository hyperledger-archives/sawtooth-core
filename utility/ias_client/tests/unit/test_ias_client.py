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

import json
import unittest

import requests

from sawtooth_ias_client.ias_client import IasClient
import mock_ias_server

URL = "http://127.0.0.1:8008"


class TestIasClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mock_server = mock_ias_server.create(URL)
        cls.mock_server.start("up")

    @classmethod
    def tearDownClass(cls):
        cls.mock_server.stop()

    def test_up(self):
        """Verify that the client behaves as expected when the IAS server is
           functioning properly.
        """
        self.mock_server.restart("up")
        client = IasClient(URL, None, 5)

        siglist = client.get_signature_revocation_lists(gid="gid")
        received = self.mock_server.get_received()

        self.assertEqual(received["command"], "GET")
        self.assertEqual(received["path"], "/attestation/sgx/v2/sigrl/gid")
        self.assertEqual(siglist, "thisisasignaturelist")

        verification = client.post_verify_attestation(
            "thisisaquote", "thisisamanifest", 34608138615
        )
        received = self.mock_server.get_received()
        received_data = json.loads(received["data"].decode())

        self.assertEqual(received["command"], "POST")
        self.assertEqual(received["path"], "/attestation/sgx/v2/report")
        self.assertEqual(received_data, {
            "isvEnclaveQuote": "thisisaquote",
            "pseManifest": "thisisamanifest",
            "nonce": 34608138615,
        })
        self.assertEqual(verification, {
            "verification_report": '{"thisisa":"verification_report"}',
            "signature": "signature",
        })

    def test_error(self):
        """Verify that the client behaves as expected when the IAS server
           returns an HTTP status code that is an error.
        """
        self.mock_server.restart("error")
        client = IasClient(URL, None, 5)
        self.assertRaises(requests.HTTPError,
                          client.get_signature_revocation_lists)
        self.assertRaises(requests.HTTPError,
                          client.post_verify_attestation, "")

    def test_slow(self):
        """Verify that the client throws a timeout error if the IAS server is
           slow to respond.
        """
        self.mock_server.restart("slow")
        client = IasClient(URL, None, 0.1)
        self.assertRaises(requests.exceptions.Timeout,
                          client.get_signature_revocation_lists)
        self.assertRaises(requests.exceptions.Timeout,
                          client.post_verify_attestation, "")

    def test_down(self):
        """Verify that the client throws a connection error if the IAS server
           doesn't repond correctly.
        """
        self.mock_server.restart("down")
        client = IasClient(URL, None, 5)
        self.assertRaises(requests.exceptions.ConnectionError,
                          client.get_signature_revocation_lists)
        self.assertRaises(requests.exceptions.ConnectionError,
                          client.post_verify_attestation, "")

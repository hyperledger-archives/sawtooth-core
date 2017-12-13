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

from aiohttp.test_utils import unittest_run_loop

from components import BaseApiTest
from sawtooth_rest_api.protobuf.validator_pb2 import Message
from sawtooth_rest_api.protobuf import client_peers_pb2


class PeersGetRequestTests(BaseApiTest):
    async def get_application(self):
        self.set_status_and_connection(
            Message.CLIENT_PEERS_GET_REQUEST,
            client_peers_pb2.ClientPeersGetRequest,
            client_peers_pb2.ClientPeersGetResponse)

        handlers = self.build_handlers(self.loop, self.connection)
        return self.build_app(self.loop, '/peers', handlers.fetch_peers)

    @unittest_run_loop
    async def test_peers_request(self):
        """Verifies a GET /peers works proberly.

        It will receive a Protobuf response with:
            - list of peer endoints

        It should send an empty Protobuf request.

        It should send back a JSON response with:
            - a response status of 200
            - a link property that ends in '/peers'
            - a data property matching the peers
        """
        self.connection.preset_response(
            peers=["Peer1", "Peer2"],
            status=self.status.OK)

        response = await self.get_assert_200('/peers')
        self.connection.assert_valid_request_sent()

        self.assert_has_valid_link(response, '/peers')
        self.assertEqual(["Peer1", "Peer2"], response['data'])

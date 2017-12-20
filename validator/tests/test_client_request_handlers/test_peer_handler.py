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

import sawtooth_validator.state.client_handlers as handlers
from sawtooth_validator.protobuf import client_peers_pb2
from test_client_request_handlers.base_case import ClientHandlerTestCase
from test_client_request_handlers.mocks import MockGossip


class TestPeerRequests(ClientHandlerTestCase):
    def setUp(self):
        gossip = MockGossip()
        self.initialize(
            handlers.PeersGetRequest(gossip),
            client_peers_pb2.ClientPeersGetRequest,
            client_peers_pb2.ClientPeersGetResponse,
        )

    def test_peer_request(self):
        """Verifies requests for peers work properly.

        Queries the default mock gossip for peers. Expecting "Peer1"

        Expects to find:
            - a status of OK
            - a head_id of 'bbb...2' (the latest)
            - the default paging response, showing all 3 resources returned
            - a list of blocks with 3 items
            - the items are instances of Block
            - The first item has a header_signature of 'bbb...2'
        """
        response = self.make_request()

        self.assertEqual(self.status.OK, response.status)
        self.assertEqual(["Peer1"], response.peers)

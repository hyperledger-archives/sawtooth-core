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

from concurrent.futures import ThreadPoolExecutor
import unittest

from sawtooth_validator.networking import dispatch
from sawtooth_validator.protobuf import validator_pb2

from test_dispatcher.mock import MockSendMessage
from test_dispatcher.mock import MockHandler1
from test_dispatcher.mock import MockHandler2


class TestDispatcherIdentityMessageMatch(unittest.TestCase):
    def setUp(self):
        self._connection = "TestConnection"
        self._dispatcher = dispatch.Dispatcher()
        thread_pool = ThreadPoolExecutor()

        self._dispatcher.add_handler(
            validator_pb2.Message.DEFAULT,
            MockHandler1(),
            thread_pool)
        self._dispatcher.add_handler(
            validator_pb2.Message.DEFAULT,
            MockHandler2(),
            thread_pool)

        self._message_ids = [str(i) for i in range(10)]
        self._identities = [str(i) for i in range(10)]
        self._connections = {chr(int(x) + 65): x for x in self._identities}

        self.mock_send_message = MockSendMessage(self._connections)
        self._dispatcher.add_send_message(self._connection,
                                          self.mock_send_message.send_message)

        self._messages = [
            validator_pb2.Message(
                content=validator_pb2.Message(
                    correlation_id=m_id).SerializeToString(),
                message_type=validator_pb2.Message.DEFAULT)
            for m_id in self._message_ids
        ]

    def test_correct_identity(self):
        """Tests that if a message is dispatched with a particular identity --
        having dispatcher.dispatch(connection, message, connection_id)
        called -- that identity will be sent back to the zmq interface
        with the message.

        Each message gets an id 0-9 along with an identity 0-9. These will
        be returned to send_message together no matter the ordering of the
        returns of the handlers.

        """
        self._dispatcher.start()
        for connection_id, message in zip(self._connections, self._messages):
            self._dispatcher.dispatch(
                self._connection, message, connection_id)
        self._dispatcher.block_until_complete()
        self.assertEqual(sorted(self.mock_send_message.message_ids),
                         sorted(self.mock_send_message.identities))

    def tearDown(self):
        self._dispatcher.stop()

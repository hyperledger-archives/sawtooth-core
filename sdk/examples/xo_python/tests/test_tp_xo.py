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

from sawtooth_processor_test.transaction_processor_test_case \
    import TransactionProcessorTestCase
from sawtooth_xo.xo_message_factory import XoMessageFactory


class TestXo(TransactionProcessorTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.xomf = XoMessageFactory()

    def test_create_game(self):
        tst = self.tester
        xomf = self.xomf

        tst.send(xomf.create_tp_process_request("game000", "create"))
        received = tst.expect(xomf.create_get_request("game000"))

        tst.respond(xomf.create_get_response("game000", None), received)
        received = tst.expect(xomf.create_set_request("game000"))

        tst.respond(xomf.create_set_response("game000"), received)
        tst.expect(xomf.create_tp_response("OK"))

    def test_take_space(self):
        tst = self.tester
        xomf = self.xomf

        tst.send(xomf.create_tp_process_request("game000", "take", 3))
        received = tst.expect(xomf.create_get_request("game000"))

        tst.respond(xomf.create_get_response("game000"), received)

        received = tst.expect(xomf.create_set_request(
            "game000", "--X------", "P2-NEXT", xomf.get_public_key(), ""
        ))
        tst.respond(xomf.create_set_response("game000"), received)
        tst.expect(xomf.create_tp_response("OK"))

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

import logging
from sawtooth.client import SawtoothClient

from ledger.transaction import integer_key

logger = logging.getLogger(__name__)


class IntegerKeyClient(SawtoothClient):
    def __init__(self,
                 baseurl,
                 name='IntegerKeyClient',
                 keystring=None,
                 keyfile=None,
                 state=None):
        super(IntegerKeyClient, self).__init__(
            base_url=baseurl,
            name=name,
            store_name="IntegerKeyTransaction",
            transaction_type=integer_key.IntegerKeyTransaction,
            message_type=integer_key.IntegerKeyTransaction.MessageType,
            keystring=keystring,
            keyfile=keyfile)

        # Compatibility shim until the integration and smoke tests get
        # refactored.
        self.waitforcommit = self.wait_for_commit
        self.headrequest = self.get_transaction_status

    def _sendtxn(self, update, txndep=None, postmsg=True):
        """
        Compatibility shim until the integration and smoke tests get
         refactored.
        """
        minfo = {"Updates": [update.dump()]}
        if txndep:
            minfo["Dependencies"] = [txndep]

        return self.sendtxn(
            txn_type=integer_key.IntegerKeyTransaction,
            txn_msg_type=integer_key.IntegerKeyTransaction.MessageType,
            minfo=minfo)

    def set(self, key, value, txndep=None, postmsg=True):
        """Creates an update object which sets the value associated with a key.

               Args:
                   key (str): The key to set.
                   value (int): The value to set for key.
        """
        update = integer_key.Update({
            "Verb": "set",
            "Name": key,
            "Value": value
        })

        return self._sendtxn(update, txndep, postmsg)

    def inc(self, key, value, txndep=None, postmsg=True):
        """Creates an update object which increments the value associated with
           a key.
               Args:
                   key (str): The key to set.
                   value (int): The value by which to increment the current
                       value associated with key.
        """
        update = integer_key.Update({
            "Verb": "inc",
            "Name": key,
            "Value": value
        })

        return self._sendtxn(update, txndep, postmsg)

    def dec(self, key, value, txndep=None, postmsg=True):
        """Creates an update object which decrements the value associated with
           a key.
               Args:
                   key (str): The key to set.
                   value (int): The value by which to decrement the current
                       value associated with key.
        """
        update = integer_key.Update({
            "Verb": "dec",
            "Name": key,
            "Value": value
        })

        return self._sendtxn(update, txndep, postmsg)

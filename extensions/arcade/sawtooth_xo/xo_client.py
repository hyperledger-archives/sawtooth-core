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

from sawtooth.client import SawtoothClient

from sawtooth_xo.txn_family import XoTransaction


class XoClient(SawtoothClient):
    def __init__(self,
                 base_url,
                 keyfile,
                 disable_client_validation=False):
        super(XoClient, self).__init__(
            base_url=base_url,
            store_name='XoTransaction',
            name='XoClient',
            transaction_type=XoTransaction,
            message_type=XoTransaction.MessageType,
            keyfile=keyfile,
            disable_client_validation=disable_client_validation)

    def create(self, name):
        """
        """
        update = {
            'Action': 'CREATE',
            'Name': name
        }

        return self.sendtxn(XoTransaction, XoTransaction.MessageType, update)

    def take(self, name, space):
        """
        """
        update = {
            'Action': 'TAKE',
            'Name': name,
            'Space': space,
        }

        return self.sendtxn(XoTransaction, XoTransaction.MessageType, update)

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


class MockNetwork():
    def __init__(self, roles, allow_inbound=True, is_outbound=False,
                 connection_status=None):
        self.roles = roles
        self.allow_inbound = allow_inbound
        self.is_outbound = is_outbound
        if connection_status is None:
            self._connection_status = {}
        else:
            self._connection_status = connection_status

    def update_connection_endpoint(self, connection_id, endpoint):
        pass

    def is_outbound_connection(self, connection_id):
        return self.is_outbound

    def allow_inbound_connection(self):
        return self.allow_inbound

    def update_connection_status(self, connection_id, status):
        pass

    def get_connection_status(self, connection_id):
        return self._connection_status.get(connection_id)

    def update_connection_public_key(self, connection_id, public_key):
        pass

    def send_connect_request(self, connection_id):
        pass

    def remove_connection(self, connection_id):
        pass


class MockPermissionVerifier():
    def __init__(self, allow=True):
        self.allow = allow

    def check_network_role(self, public_key):
        return self.allow


class MockGossip():
    def __init_(self):
        pass

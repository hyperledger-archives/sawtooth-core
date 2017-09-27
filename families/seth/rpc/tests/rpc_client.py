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

import threading
import time
import requests


class RpcClient:
    def __init__(self, url):
        self.url = url
        self.id = 1
        self.result = None
        self.thread = None

    def wait_for_service(self):
        while True:
            try:
                requests.get(self.url)
                return
            except requests.ConnectionError:
                time.sleep(0.2)

    def call(self, method, params=None):
        request = {"jsonrpc": "2.0", "method": method, "id": self.id}
        if params:
            request["params"] = params
        self.id += 1
        response = requests.post(self.url, json=request).json()
        try:
            return response['result']
        except KeyError:
            return response

    def acall(self, method, params=None):
        def _acall(self):
            self.result = self.call(method, params)
        self.thread = threading.Thread(target=_acall, args=(self,))
        self.thread.start()

    def get_result(self):
        self.thread.join()
        return self.result

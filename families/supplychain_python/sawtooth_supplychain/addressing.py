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

import hashlib
import time


def get_namespace():
    return hashlib.sha512('Supplychain'.encode()).hexdigest()[0:6]


def decode_offset(addr):
    if addr[6] == '0':
        return 'Record'
    elif addr[6] == '1':
        return 'Sensor'
    elif addr[6] == '2':
        return 'Agent'
    return 'Other'


def get_store_index(store, uid):
    idx = store + "." + uid

    if store == "Record":
        offset = '0'
    elif store == "Sensor":
        offset = '1'
    elif store == "Agent":
        offset = '2'
    else:
        offset = '3'

    addr = (get_namespace() + offset +
            hashlib.sha512(idx.encode()).hexdigest()[0:63])
    return get_namespace() + addr


def get_record_index(uid):
    return get_store_index("Record", uid)


def get_sensor_index(uid):
    return get_store_index("Sensor", uid)


def get_agent_index(uid):
    return get_store_index("Agent", uid)


def get_agent_id(public_key):
    address = hashlib.sha512(public_key.encode()).hexdigest()
    return get_namespace() + address


def create_record_id(data):
    address = data + str(time.time())
    address = hashlib.sha512(address.encode()).hexdigest()
    return get_namespace() + address

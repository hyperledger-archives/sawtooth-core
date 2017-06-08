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


SUPPLYCHAIN_AGENT_NAMESPACE = 'supplychain.agent'
SUPPLYCHAIN_APPLICATION_NAMESPACE = 'supplychain.application'
SUPPLYCHAIN_RECORD_NAMESPACE = 'supplychain.record'


class Addressing(object):
    _agent_namespace = None
    _application_namespace = None
    _record_namespace = None

    @classmethod
    def agent_namespace(cls):
        if cls._agent_namespace is None:
            cls._agent_namespace = hashlib.sha512(
                SUPPLYCHAIN_AGENT_NAMESPACE.encode()).hexdigest()[0:6]
        return cls._agent_namespace

    @classmethod
    def agent_address(cls, public_key):
        address = hashlib.sha512(public_key.encode()).hexdigest()[0:64]
        return cls.agent_namespace() + address

    @classmethod
    def application_namespace(cls):
        if cls._application_namespace is None:
            cls._application_namespace = hashlib.sha512(
                SUPPLYCHAIN_APPLICATION_NAMESPACE.encode()).hexdigest()[0:6]

        return cls._application_namespace

    @classmethod
    def application_address(cls, record_identifier):
        address = hashlib.sha512(record_identifier.encode()).hexdigest()[0:64]
        return cls.application_namespace() + address

    @classmethod
    def record_namespace(cls):
        if cls._record_namespace is None:
            cls._record_namespace = hashlib.sha256(
                SUPPLYCHAIN_RECORD_NAMESPACE.encode()).hexdigest()[0:6]

        return cls._record_namespace

    @classmethod
    def record_address(cls, identifier):
        address = hashlib.sha512(identifier.encode()).hexdigest()[0:64]
        return cls.record_namespace() + address

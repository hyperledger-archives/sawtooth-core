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

import logging
import os
import unittest
from unittest.mock import MagicMock

from sawtooth_supplychain.cli.init import do_init
from sawtooth_supplychain.cli.main import load_config

from sawtooth_supplychain.client import SupplyChainClient
from sawtooth_supplychain.protobuf.agent_pb2 import Agent
from sawtooth_supplychain.protobuf.application_pb2 import Application
from sawtooth_supplychain.protobuf.record_pb2 import Record


LOGGER = logging.getLogger(__name__)


def dump_protobuf(obj):
    for descriptor in obj.DESCRIPTOR.fields:
        value = getattr(obj, descriptor.name)
        if descriptor.type == descriptor.TYPE_MESSAGE:
            if descriptor.label == descriptor.LABEL_REPEATED:
                map(dump_protobuf, value)
            else:
                dump_protobuf(value)
        elif descriptor.type == descriptor.TYPE_ENUM:
            enum_name = descriptor.enum_type.values[value].name
            logging.debug("%s: %s", descriptor.full_name, enum_name)
        else:
            logging.debug("%s: %s", descriptor.full_name, value)


def _compare_protobufs(left, right):
    if left.SerializeToString() != right.SerializeToString():
        logging.debug("left %s", left.SerializeToString())
        dump_protobuf(left)
        logging.debug("right %s", right.SerializeToString())
        dump_protobuf(right)
        return False
    return True


def _compare_protobufs_list(left, right):
    if len(left) == len(right):
        # pylint: disable=consider-using-enumerate
        for i in range(len(left)):
            if not _compare_protobufs(left[i], right[i]):
                return False
        return True
    logging.debug("left and right are not the same size. %s != %s",
                  len(left), len(right))
    logging.debug("left %s", left)
    logging.debug("right %s", right)
    return False


class TestSupplyChainIntegration(unittest.TestCase):
    def setUp(self):
        self.client = self.create_client()

    def create_client(self):
        args = MagicMock()
        args.username = None
        args.url = None
        config = load_config()
        # Every test runs with a new key, so we must remove existing
        # files
        key_file = config.get('DEFAULT', 'key_file')
        if os.path.exists(key_file):
            os.remove(key_file)
        do_init(args, config)
        config = load_config()

        url = os.environ.get('RESTAPI_URL', config.get('DEFAULT', 'url'))
        key_file = config.get('DEFAULT', 'key_file')
        return SupplyChainClient(url, key_file)

    def _agent(self, name, key=None):
        return Agent(identifier=key or self.client.public_key,
                     name="test")

    def _record(self, record_id, creation_time, public_key=None):
        public_key = public_key or self.client.public_key
        return Record(
            identifier=record_id,
            creation_time=creation_time,
            owners=[Record.AgentRecord(agent_identifier=public_key,
                                       start_time=creation_time)],
            custodians=[Record.AgentRecord(agent_identifier=public_key,
                                           start_time=creation_time)]
        )

    def _application(self, record_id, public_key,
                     creation_time, app_type=Application.OWNER,
                     app_status=Application.OPEN):
        return Application(
            record_identifier=record_id,
            applicant=public_key,
            creation_time=creation_time,
            type=Application.OWNER,
            status=Application.OPEN
        )

    def test_agent(self):
        '''Test that an agent can be created via the client.
        '''
        name = "test"
        ref_agent = self._agent(name)
        self.client.agent_create(name, wait=5)
        agent_list = self.client.agent_list()
        self.expect_equal([ref_agent], agent_list)
        agent = self.client.agent_get(self.client.public_key)
        self.expect_equal(ref_agent, agent)

    def test_record(self):
        '''Test that a Record can be created and finalized via the client.
        '''
        record_id = 'test_record'
        creation_time = 45464747
        ref_record = self._record(record_id, creation_time)
        self.client.agent_create("test", wait=5)
        self.client.record_create(record_id, creation_time=creation_time,
                                  wait=5)
        record_list = self.client.record_list()
        # we can only check this record is as we expect since
        # other tests have added records to the state.
        record = self._find_record(record_id, record_list)
        self.expect_equal(ref_record, record)
        record = self.client.record_get(record_id)
        self.expect_equal(ref_record, record)

        self.client.record_finalize(record_id, wait=5)
        ref_record.final = True
        record = self.client.record_get(record_id)
        self.expect_equal(ref_record, record)

    def test_application(self):
        '''Test that an Application can be created and accepted via the client.
        '''
        client2 = self.create_client()

        record_id = 'test_record_application'
        public_key = client2.public_key
        creation_time = 45464747
        ref_application = self._application(
            record_id, public_key, creation_time)

        self.client.agent_create("test", wait=5)
        client2.agent_create("test", wait=5)
        self.client.record_create(record_id, wait=5)

        client2.application_create(record_id, Application.OWNER,
                                   creation_time=creation_time, wait=5)

        application_list = self.client.application_list()
        self.expect_equal([ref_application], application_list)

        application = self.client.application_get(record_id, public_key,
                                                  Application.OWNER)
        self.expect_equal(ref_application, application)

        self.client.application_accept(record_id, public_key,
                                       Application.OWNER,
                                       timestamp=creation_time,
                                       wait=5)
        application = self.client.application_get(record_id, public_key,
                                                  Application.OWNER)
        ref_application.status = Application.ACCEPTED
        self.expect_equal(ref_application, application)

    def test_application_reject(self):
        '''Test that an Application can be rejected via the client.
        '''
        client2 = self.create_client()

        record_id = 'test_record_reject'
        public_key = client2.public_key
        creation_time = 45464747
        ref_application = self._application(
            record_id, public_key, creation_time)

        self.client.agent_create("test", wait=5)
        client2.agent_create("test", wait=5)
        self.client.record_create(record_id, wait=5)

        client2.application_create(record_id, Application.OWNER,
                                   creation_time=creation_time, wait=5)

        application_list = self.client.application_list()
        application = self._find_application(record_id, public_key,
                                             Application.OWNER,
                                             application_list)
        self.expect_equal(ref_application, application)

        application = self.client.application_get(record_id, public_key,
                                                  Application.OWNER)
        self.expect_equal(ref_application, application)

        self.client.application_reject(record_id, public_key,
                                       Application.OWNER, wait=5)
        application = self.client.application_get(record_id, public_key,
                                                  Application.OWNER)
        ref_application.status = Application.REJECTED
        self.expect_equal(ref_application, application)

    def test_application_cancel(self):
        '''Test that an Application can be canceled via the client.
        '''
        client2 = self.create_client()

        record_id = 'test_record_cancel'
        public_key = client2.public_key
        creation_time = 45464747
        ref_application = self._application(
            record_id, public_key, creation_time)

        self.client.agent_create("test", wait=5)
        client2.agent_create("test", wait=5)
        self.client.record_create(record_id, wait=5)

        client2.application_create(record_id, Application.OWNER,
                                   creation_time=creation_time, wait=5)

        application_list = self.client.application_list()
        application = self._find_application(record_id, public_key,
                                             Application.OWNER,
                                             application_list)
        self.expect_equal(ref_application, application)

        application = self.client.application_get(record_id, public_key,
                                                  Application.OWNER)
        self.expect_equal(ref_application, application)

        client2.application_cancel(record_id, Application.OWNER,
                                   wait=5)
        application = self.client.application_get(record_id, public_key,
                                                  Application.OWNER)
        ref_application.status = Application.CANCELED
        self.expect_equal(ref_application, application)

    @staticmethod
    def _find_record(record_identifier, record_list):
        for record in record_list:
            if record.identifier == record_identifier:
                return record
        return None

    @staticmethod
    def _find_application(record_id, applicant,
                          application_type,
                          application_list):
        for app in application_list:
            if app.record_identifier == record_id and \
                    app.applicant == applicant and \
                    app.type == application_type:
                return app
        return None

    def expect_equal(self, left, right):
        if isinstance(left, list):
            self.assertTrue(_compare_protobufs_list(left, right))
        else:
            self.assertTrue(_compare_protobufs(left, right))

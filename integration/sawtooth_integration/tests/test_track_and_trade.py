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
import unittest

from sawtooth_integration.tests.integration_tools import RestClient
from sawtooth_integration.tests.integration_tools import wait_for_rest_apis

from sawtooth_tt_test.track_and_trade_message_factory import \
    TrackAndTradeMessageFactory

import sawtooth_track_and_trade.addressing as addressing
from sawtooth_track_and_trade.protobuf.property_pb2 import PropertySchema
from sawtooth_track_and_trade.protobuf.proposal_pb2 import Proposal
from sawtooth_track_and_trade.protobuf.payload_pb2 import AnswerProposalAction


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


REST_API = 'rest-api:8080'
URL = 'http://' + REST_API


NARRATION = False


class TTClient(RestClient):
    def __init__(self, url=URL):
        self.factory = TrackAndTradeMessageFactory()
        self.public_key = self.factory.public_key
        super().__init__(
            url=url,
            namespace=addressing.NAMESPACE)

    def _post_tt_transaction(self, transaction):
        return self.send_batches(
            self.factory.create_batch(
                transaction))

    def create_agent(self, name):
        return self._post_tt_transaction(
            self.factory.create_agent(
                name))

    def create_record_type(self, name, *properties):
        return self._post_tt_transaction(
            self.factory.create_record_type(
                name, *properties))

    def create_record(self, record_id, record_type, properties_dict):
        return self._post_tt_transaction(
            self.factory.create_record(
                record_id, record_type, properties_dict))

    def finalize_record(self, record_id):
        return self._post_tt_transaction(
            self.factory.finalize_record(
                record_id))

    def update_properties(self, record_id, properties_dict):
        return self._post_tt_transaction(
            self.factory.update_properties(
                record_id, properties_dict))

    def create_proposal(self, record_id, receiving_agent,
                        role, properties=None):
        if properties is None:
            properties = []

        return self._post_tt_transaction(
            self.factory.create_proposal(
                record_id, receiving_agent, role, properties))

    def answer_proposal(self, record_id, role, response, receiving_agent=None):
        if receiving_agent is None:
            receiving_agent = self.public_key

        return self._post_tt_transaction(
            self.factory.answer_proposal(
                record_id=record_id,
                receiving_agent=receiving_agent,
                role=role,
                response=response))

    def send_empty_payload(self):
        return self._post_tt_transaction(
            self.factory.make_empty_payload(
                self.public_key))


class TestTrackAndTrade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wait_for_rest_apis([REST_API])

    def assert_valid(self, result):
        try:
            self.assertEqual(1, len(result))
            self.assertIn('link', result)
        except AssertionError:
            raise AssertionError(
                'Transaction is unexpectedly invalid -- {}'.format(
                    result['data'][0]['invalid_transactions'][0]['message']))

    def assert_invalid(self, result):
        self.narrate('{}', result)
        try:
            self.assertEqual(
                'INVALID',
                result['data'][0]['status'])
        except (KeyError, IndexError):
            raise AssertionError(
                'Transaction is unexpectedly valid')

    def narrate(self, message, *interpolations):
        if NARRATION:
            LOGGER.info(
                message.format(
                    *interpolations))

    def test_track_and_trade(self):
        jin = TTClient()

        self.assert_invalid(
            jin.send_empty_payload())

        self.narrate(
            '''
            Jin tries to create a record for a fish with label `fish-456`.
            ''')

        self.assert_invalid(
            jin.create_record(
                'fish-456',
                'fish',
                {}))

        self.narrate(
            '''
            Only registered agents can create records, so
            Jin registers as an agent with public key {}.
            ''',
            jin.public_key[:6])

        self.assert_valid(
            jin.create_agent('Jin Kwon'))

        self.narrate(
            '''
            He can't register as an agent again because there is already an
            agent registerd with his key (namely, himself).
            ''')

        self.assert_invalid(
            jin.create_agent('Jin Kwon'))

        self.narrate(
            '''
            Jin tries to create a record for a fish with label `fish-456`.
            ''')

        self.assert_invalid(
            jin.create_record(
                'fish-456',
                'fish',
                {}))

        self.narrate(
            '''
            He said his fish record should have type `fish`, but that
            type doesn't exist yet. He needs to create the `fish`
            record type first.
            ''')

        self.narrate(
            '''
            Jin creates the record type `fish` with properties {}.
            Subsequent attempts to create a type with that name will
            fail.
            ''',
            ['species', 'weight', 'temperature', 'latitude', 'longitude'])

        self.assert_valid(
            jin.create_record_type(
                'fish',
                ('species', PropertySchema.STRING, True),
                ('weight', PropertySchema.INT, True),
                ('temperature', PropertySchema.INT, False),
                ('latitude', PropertySchema.INT, False),
                ('longitude', PropertySchema.INT, False),
            ))

        self.assert_invalid(
            jin.create_record_type(
                'fish',
                ('blarg', PropertySchema.FLOAT, True),
            ))

        self.narrate(
            '''
            Now that the `fish` record type is created, Jin can create
            his fish record.
            ''')

        self.assert_invalid(
            jin.create_record(
                'fish-456',
                'fish',
                {}))

        self.narrate(
            '''
            This time, Jin's attempt to create a record failed because
            he neglected to include initial property values for the
            record type's require properties. In this case, a `fish`
            record cannot be created without value for the properties
            `species` and `weight`.
            ''')

        self.assert_invalid(
            jin.create_record(
                'fish-456',
                'fish',
                {'species': 'trout', 'weight': 5.1}))

        self.narrate(
            '''
            Jin gave the value 5.1 for the property `weight`, but the
            type for that property is required to be int. When he
            provides a string value for `species` and an int value for
            `weight`, the record can be successfully created.
            ''')

        self.assert_valid(
            jin.create_record(
                'fish-456',
                'fish',
                {'species': 'trout', 'weight': 5}))

        self.narrate(
            '''
            Jin updates the fish record's temperature. Updates, of
            course, can only be made to the type-specified properties
            of existing records, and the type of the update value must
            match the type-specified type.
            ''')

        self.assert_valid(
            jin.update_properties(
                'fish-456',
                {'temperature': 4}))

        self.assert_invalid(
            jin.update_properties(
                'fish-456',
                {'temperature': '4'}))

        self.assert_invalid(
            jin.update_properties(
                'fish-456',
                {'splecies': 'tluna'}))

        self.assert_invalid(
            jin.update_properties(
                'fish-???',
                {'species': 'flounder'}))

        self.narrate(
            '''
            Jin updates the temperature again.
            ''')

        self.assert_valid(
            jin.update_properties(
                'fish-456',
                {'temperature': 3}))

        self.narrate(
            '''
            Jin gets tired of sending fish updates himself, so he decides to
            get an autonomous IoT sensor to do it for him.
            ''')

        sensor_stark = TTClient()

        self.assert_invalid(
            sensor_stark.update_properties(
                'fish-456',
                {'temperature': 3}))

        self.narrate(
            '''
            To get his sensor to be able to send updates, Jin has to send it a
            proposal to authorize it as a reporter for some properties
            for his record.
            ''')

        self.assert_invalid(
            jin.create_proposal(
                record_id='fish-456',
                receiving_agent=sensor_stark.public_key,
                role=Proposal.REPORTER,
                properties=['temperature'],
            ))

        self.narrate(
            '''
            This requires that the sensor be registered as an agent,
            just like Jin.
            ''')

        self.assert_valid(
            sensor_stark.create_agent(
                'sensor-stark'))

        self.assert_valid(
            jin.create_proposal(
                record_id='fish-456',
                receiving_agent=sensor_stark.public_key,
                role=Proposal.REPORTER,
                properties=['temperature'],
            ))

        self.assert_invalid(
            sensor_stark.update_properties(
                'fish-456',
                {'temperature': 3}))

        self.narrate(
            '''
            There's one last step before the sensor can send updates:
            it has to "accept" the proposal.
            ''')

        self.assert_valid(
            sensor_stark.answer_proposal(
                record_id='fish-456',
                role=Proposal.REPORTER,
                response=AnswerProposalAction.ACCEPT,
            ))

        self.assert_invalid(
            sensor_stark.answer_proposal(
                record_id='fish-456',
                role=Proposal.REPORTER,
                response=AnswerProposalAction.ACCEPT,
            ))

        self.narrate(
            '''
            Now that it is an authorized reporter, the sensor can
            start sending updates.
            ''')

        for i in range(5):
            self.assert_valid(
                sensor_stark.update_properties(
                    'fish-456',
                    {'temperature': i}))

        self.narrate(
            '''
            Jin would like to sell his fish to Sun, a fish dealer. Of
            course, Sun must also be registered as an agent. After she
            registers, Jin can propose to transfer ownership to her
            (with payment made off-chain).
            ''')

        sun = TTClient()

        self.assert_invalid(
            jin.create_proposal(
                record_id='fish-456',
                role=Proposal.OWNER,
                receiving_agent=sun.public_key,
            ))

        self.assert_valid(
            sun.create_agent(name='Sun Kwon'))

        self.assert_valid(
            jin.create_proposal(
                record_id='fish-456',
                role=Proposal.OWNER,
                receiving_agent=sun.public_key,
            ))

        self.narrate(
            '''
            Jin has second thoughts and cancels his proposal. Sun and
            her lawyers convince him to change his mind back, so he
            opens a new proposal.
            ''')

        self.assert_valid(
            jin.answer_proposal(
                record_id='fish-456',
                role=Proposal.OWNER,
                response=AnswerProposalAction.CANCEL,
                receiving_agent=sun.public_key,
            ))

        self.assert_invalid(
            sun.answer_proposal(
                record_id='fish-456',
                role=Proposal.OWNER,
                response=AnswerProposalAction.ACCEPT,
            ))

        self.assert_valid(
            jin.create_proposal(
                record_id='fish-456',
                role=Proposal.OWNER,
                receiving_agent=sun.public_key,
            ))

        self.assert_valid(
            sun.answer_proposal(
                record_id='fish-456',
                role=Proposal.OWNER,
                response=AnswerProposalAction.ACCEPT,
            ))

        self.assert_invalid(
            sun.answer_proposal(
                record_id='fish-456',
                role=Proposal.OWNER,
                response=AnswerProposalAction.ACCEPT,
            ))

        self.assert_invalid(
            jin.create_proposal(
                record_id='fish-456',
                role=Proposal.OWNER,
                receiving_agent=sun.public_key,
            ))

        self.narrate(
            '''
            Sun wants to finalize the record to prevent any further updates.
            ''')

        self.assert_invalid(
            sun.finalize_record('fish-456'))

        self.narrate(
            '''
            In order to finalize a record, the owner and the custodian
            must be the same person. Sun is the owner of the fish in a
            legal sense, but Jin is still the custodian (that is, he
            has physical custody of it). Jin hands over the fish.
            ''')

        self.assert_valid(
            jin.create_proposal(
                record_id='fish-456',
                role=Proposal.CUSTODIAN,
                receiving_agent=sun.public_key,
            ))

        self.assert_valid(
            sun.answer_proposal(
                record_id='fish-456',
                role=Proposal.CUSTODIAN,
                response=AnswerProposalAction.ACCEPT,
            ))

        self.assert_valid(
            sun.finalize_record('fish-456'))

        self.assert_invalid(
            sun.finalize_record('fish-456'))

        self.assert_invalid(
            jin.update_properties(
                'fish-456',
                {'temperature': 2}))

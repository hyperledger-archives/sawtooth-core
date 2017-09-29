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

import json
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

NARRATION = False


REST_API = 'rest-api:8081'
URL = 'http://' + REST_API

SERVER_URL = 'http://tnt-server:3000'
API = SERVER_URL + '/api'


class TTClient(RestClient):
    def __init__(self, url=URL):
        self.factory = TrackAndTradeMessageFactory()
        self.public_key = self.factory.public_key
        self.private_key = self.factory.private_key

        self.auth_token = None

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

    def revoke_reporter(self, record_id, reporter_id, properties):
        return self._post_tt_transaction(
            self.factory.revoke_reporter(
                record_id, reporter_id, properties))

    def send_empty_payload(self):
        return self._post_tt_transaction(
            self.factory.make_empty_payload(
                self.public_key))

    def get_agents(self, fields=None, omit=None):
        return self._submit_request(
            url='{}/agents{}'.format(
                API,
                make_query_string(fields, omit))
        )[1]

    def get_agent(self, public_key, fields=None, omit=None):
        return self._submit_request(
            url='{}/agents/{}{}'.format(
                API,
                public_key,
                make_query_string(fields, omit)),
            headers={'Authorization': self.auth_token},
        )[1]

    def get_records(self, fields=None, omit=None):
        return self._submit_request(
            url='{}/records{}'.format(
                API,
                make_query_string(fields, omit)),
            headers={'Authorization': self.auth_token}
        )[1]

    def get_record(self, record_id, fields=None, omit=None):
        return self._submit_request(
            url='{}/records/{}{}'.format(
                API,
                record_id,
                make_query_string(fields, omit)),
            headers={'Authorization': self.auth_token}
        )[1]

    def get_record_property(self, record_id, property_name,
                            fields=None, omit=None):
        return self._submit_request(
            url='{}/records/{}/property/{}{}'.format(
                API,
                record_id,
                property_name,
                make_query_string(fields, omit))
        )[1]

    def post_user(self, username):
        response = self._submit_request(
            url=SERVER_URL + '/api/users',
            method='POST',
            headers={'Content-Type': 'application/json'},
            data=json.dumps({
                'username': username,
                'email': '{}@website.com'.format(username),
                'password': '{}pass'.format(username),
                'publicKey': self.public_key,
                'encryptedKey': self.private_key,
            }),
        )

        if self.auth_token is None:
            self.auth_token = response[1]['authorization']


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
            Upon transfer of ownership, Sun became a reporter on all
            of the record's properties and Jin reporter authorization
            was revoked. Jin's sensor remains authorized.
            ''')

        self.assert_invalid(
            jin.update_properties(
                'fish-456',
                {'temperature': 6}))

        self.assert_valid(
            sun.update_properties(
                'fish-456',
                {'temperature': 6}))

        self.assert_valid(
            sensor_stark.update_properties(
                'fish-456',
                {'temperature': 7}))

        self.narrate(
            '''
            Sun decides to revoke the reporter authorization of Jin's
            sensor and authorize her own sensor.
            ''')

        sensor_dollars = TTClient()

        self.assert_valid(
            sensor_dollars.create_agent(
                'sensor-dollars'))

        self.assert_valid(
            sun.create_proposal(
                record_id='fish-456',
                receiving_agent=sensor_dollars.public_key,
                role=Proposal.REPORTER,
                properties=['temperature'],
            ))

        self.assert_valid(
            sensor_dollars.answer_proposal(
                record_id='fish-456',
                role=Proposal.REPORTER,
                response=AnswerProposalAction.ACCEPT,
            ))

        self.assert_valid(
            sensor_dollars.update_properties(
                'fish-456',
                {'temperature': 8}))

        self.assert_valid(
            sun.revoke_reporter(
                record_id='fish-456',
                reporter_id=sensor_stark.public_key,
                properties=['temperature']))

        self.assert_invalid(
            sensor_stark.update_properties(
                'fish-456',
                {'temperature': 9}))

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

        self.assert_invalid(
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
            sun.update_properties(
                'fish-456',
                {'temperature': 2}))

        ###

        agents_endpoint = jin.get_agents()

        log_json(agents_endpoint)

        agents_assertion = [
            [
                agent['name'],
                agent['owns'],
                agent['custodian'],
                agent['reports'],
            ]
            for agent in
            sorted(
                agents_endpoint,
                key=lambda agent: agent['name']
            )
        ]

        self.assertEqual(
            agents_assertion,
            [
                [
                    'Jin Kwon',
                    [],
                    [],
                    [],
                ],
                [
                    'Sun Kwon',
                    ['fish-456'],
                    ['fish-456'],
                    ['fish-456'],
                ],
                [
                    'sensor-dollars',
                    [],
                    [],
                    ['fish-456'],
                ],
                [
                    'sensor-stark',
                    [],
                    [],
                    [],
                ],
            ]
        )

        jin.post_user('jin')

        agent_auth_assertion = jin.get_agent(jin.public_key)

        log_json(agent_auth_assertion)

        self.assertEqual(
            agent_auth_assertion,
            {
                'email': 'jin@website.com',
                'encryptedKey': jin.private_key,
                'name': 'Jin Kwon',
                'publicKey': jin.public_key,
                'username': 'jin',
            }
        )

        agent_no_auth_assertion = sun.get_agent(jin.public_key)

        log_json(agent_no_auth_assertion)

        self.assertEqual(
            agent_no_auth_assertion,
            {
                'name': 'Jin Kwon',
                'publicKey': jin.public_key,
            }
        )

        get_record_property = jin.get_record_property(
            'fish-456', 'temperature')

        log_json(get_record_property)

        self.assertIn('dataType', get_record_property)
        self.assertEqual(get_record_property['dataType'], 'INT')

        self.assertIn('name', get_record_property)
        self.assertEqual(get_record_property['name'], 'temperature')

        self.assertIn('recordId', get_record_property)
        self.assertEqual(get_record_property['recordId'], 'fish-456')

        self.assertIn('value', get_record_property)

        self.assertIn('reporters', get_record_property)
        self.assertEqual(len(get_record_property['reporters']), 2)

        self.assertIn('updates', get_record_property)
        self.assertEqual(len(get_record_property['updates']), 10)

        for update in get_record_property['updates']:
            self.assertIn('timestamp', update)
            self.assertIn('value', update)
            self.assertIn('reporter', update)

            reporter = update['reporter']
            self.assertEqual(len(reporter), 2)
            self.assertIn('name', reporter)
            self.assertIn('publicKey', reporter)

        get_record = jin.get_record('fish-456')

        log_json(get_record)

        self.assert_record_attributes(get_record)

        self.assertEqual(get_record['custodian'], sun.public_key)
        self.assertEqual(get_record['owner'], sun.public_key)
        self.assertEqual(get_record['recordId'], 'fish-456')

        for attr in ('latitude',
                     'longitude',
                     'species',
                     'temperature',
                     'weight'):
            self.assertIn(attr, get_record['updates']['properties'])

        get_records = jin.get_records()

        log_json(get_records)

        for record in get_records:
            self.assert_record_attributes(record)

        self.assertEqual(
            jin.get_agent(
                public_key=jin.public_key,
                fields=[
                    'publicKey',
                    'name',
                    'email',
                ]
            ),
            {
                'email': 'jin@website.com',
                'name': 'Jin Kwon',
                'publicKey': jin.public_key,
            }
        )

        self.assertEqual(
            sorted(
                jin.get_agents(
                    fields=[
                        'name',
                        'owns',
                    ]
                ),
                key=lambda agent: agent['name']
            ),
            [
                {
                    'name': 'Jin Kwon',
                    'owns': [],
                },
                {
                    'name': 'Sun Kwon',
                    'owns': ['fish-456'],
                },
                {
                    'name': 'sensor-dollars',
                    'owns': [],
                },
                {
                    'name': 'sensor-stark',
                    'owns': [],
                },
            ]
        )

        self.assertEqual(
            jin.get_record(
                record_id='fish-456',
                omit=[
                    'properties',
                    'proposals',
                    'updates',
                ]
            ),
            {
                'custodian': sun.public_key,
                'final': True,
                'owner': sun.public_key,
                'recordId': 'fish-456',
            }
        )

        self.assertEqual(
            jin.get_record_property(
                record_id='fish-456',
                property_name='weight',
                omit=[
                    'recordId',
                    'reporters',
                    'updates',
                    'value',
                ]
            ),
            {
                'dataType': 'INT',
                'name': 'weight',
            }
        )

    def assert_record_attributes(self, record):
        for attr in ('custodian',
                     'owner',
                     'properties',
                     'proposals',
                     'recordId',
                     'updates'):
            self.assertIn(attr, record)

        for prop in record['properties']:
            for attr in ('name',
                         'reporters',
                         'type',
                         'value'):
                self.assertIn(attr, prop)

        for prop in record['proposals']:
            for attr in ('issuingAgent',
                         'properties',
                         'role'):
                self.assertIn(attr, prop)

        for attr in ('custodians',
                     'owners',
                     'properties'):
            self.assertIn(attr, record['updates'])

        for associated_agent in ('custodians', 'owners'):
            for attr in ('agentId', 'timestamp'):
                for entry in record['updates'][associated_agent]:
                    self.assertIn(attr, entry)


def make_query_string(fields, omit):
    fields = '' if fields is None else '?fields=' + ','.join(fields)
    omit = '' if omit is None else '?omit=' + ','.join(omit)

    return fields if fields else omit


def log_json(msg):
    LOGGER.debug(
        json.dumps(
            msg,
            indent=4,
            sort_keys=True))


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

import unittest
import hashlib
import base64

from sawtooth_config_test.config_message_factory import ConfigMessageFactory
from sawtooth_config.protobuf.config_pb2 import ConfigCandidates
from sawtooth_config.protobuf.config_pb2 import ConfigCandidate
from sawtooth_config.protobuf.config_pb2 import ConfigVote
from sawtooth_config.protobuf.config_pb2 import ConfigProposal


def _to_hash(value):
    return hashlib.sha256(value).hexdigest()


EMPTY_CANDIDATES = ConfigCandidates(candidates=[]).SerializeToString()


class TestConfig(unittest.TestCase):
    """
    Set of tests to run in a test suite with an existing TPTester and
    transaction processor.
    """

    def __init__(self, test_name, tester):
        super().__init__(test_name)
        self.tester = tester
        self.factory = ConfigMessageFactory()

    def _expect_get(self, key, value=None):
        received = self.tester.expect(
            self.factory.create_get_request(key))
        self.tester.respond(
            self.factory.create_get_response(key, value),
            received)

    def _expect_set(self, key, expected_value):
        received = self.tester.expect(
            self.factory.create_set_request(key, expected_value))
        print('sending set response...')
        self.tester.respond(
            self.factory.create_set_response(key), received)

    def _expect_ok(self):
        self.tester.expect(self.factory.create_tp_response("OK"))

    def _expect_invalid_transaction(self):
        self.tester.expect(
            self.factory.create_tp_response("INVALID_TRANSACTION"))

    def _expect_internal_error(self):
        self.tester.expect(
            self.factory.create_tp_response("INTERNAL_ERROR"))

    def _propose(self, key, value):
        self.tester.send(self.factory.create_proposal_transaction(
            key, value, "somenonce"))

    def _vote(self, proposal_id, setting, vote):
        self.tester.send(self.factory.create_vote_proposal(
            proposal_id, setting, vote))

    @property
    def _public_key(self):
        return self.factory.public_key

    def test_set_value_no_auth(self):
        """
        Tests setting a value with no auth and no approvale type
        """
        self._propose("foo.bar.count", "1")

        self._expect_get('sawtooth.config.authorization_type', 'None')
        self._expect_get('sawtooth.config.vote.authorized_keys', '')

        # check the old value and set the new one
        self._expect_get('foo.bar.count')
        self._expect_set('foo.bar.count', '1')

        self._expect_ok()

    def test_set_value_bad_auth_type(self):
        """
        Tests setting an invalid authorization_type setting
        """
        self._propose("sawtooth.config.authorization_type", "foo")

        self._expect_get('sawtooth.config.authorization_type', 'None')
        self._expect_get('sawtooth.config.vote.authorized_keys', '')

        self._expect_invalid_transaction()

    def test_error_on_bad_auth_type(self):
        """
        Sanity test that we get back an internal error for a bad auth type.
        """
        self._propose("foo.bar.count", "1")

        self._expect_get('sawtooth.config.authorization_type', 'CrazyType')
        self._expect_get('sawtooth.config.vote.authorized_keys', '')

        self._expect_internal_error()

    def test_set_value_bad_approval_threshold(self):
        """
        Tests setting an invalid approval_threshold.
        """
        self._propose("sawtooth.config.vote.approval_threshold", "foo")

        self._expect_get('sawtooth.config.authorization_type', 'None')
        self._expect_get('sawtooth.config.vote.authorized_keys', '')

        self._expect_invalid_transaction()

    def test_set_value_proposals(self):
        """
        Tests setting the value of sawtooth.config.vote.proposals, which is
        only an internally set structure.
        """
        self._propose('sawtooth.config.vote.proposals', EMPTY_CANDIDATES)

        self._expect_get('sawtooth.config.authorization_type', 'None')
        self._expect_get('sawtooth.config.vote.authorized_keys', '')

        self._expect_invalid_transaction()

    def test_propose_in_ballot_mode(self):
        """
        Tests proposing a value in ballot mode.
        """
        self._propose('my.config.setting', 'myvalue')

        self._expect_get('sawtooth.config.authorization_type', 'Ballot')
        self._expect_get('sawtooth.config.vote.authorized_keys', '')
        self._expect_get('sawtooth.config.vote.approval_threshold', '2')
        self._expect_get('sawtooth.config.vote.proposals')

        proposal = ConfigProposal(
            setting='my.config.setting',
            value='myvalue',
            nonce='somenonce'
        )
        proposal_id = _to_hash(proposal.SerializeToString())
        record = ConfigCandidate.VoteRecord(
            public_key=self._public_key,
            vote=ConfigVote.ACCEPT)
        candidate = ConfigCandidate(
            proposal_id=proposal_id,
            proposal=proposal,
            votes=[record])

        candidates = ConfigCandidates(candidates=[candidate])

        # Get's again to update the entry
        self._expect_get('sawtooth.config.vote.proposals')
        self._expect_set('sawtooth.config.vote.proposals',
                         base64.b64encode(candidates.SerializeToString()))

        self._expect_ok()

    def test_vote_in_ballot_mode_approved(self):
        """
        Tests voting on a given setting, where the setting is approved
        """
        proposal = ConfigProposal(
            setting='my.config.setting',
            value='myvalue',
            nonce='somenonce'
        )
        proposal_id = _to_hash(proposal.SerializeToString())
        record = ConfigCandidate.VoteRecord(
            public_key="some_other_pubkey",
            vote=ConfigVote.ACCEPT)
        candidate = ConfigCandidate(
            proposal_id=proposal_id,
            proposal=proposal,
            votes=[record])

        candidates = ConfigCandidates(candidates=[candidate])

        self._vote(proposal_id, 'my.config.setting', ConfigVote.ACCEPT)

        self._expect_get('sawtooth.config.authorization_type', 'Ballot')
        self._expect_get('sawtooth.config.vote.authorized_keys', '')
        self._expect_get('sawtooth.config.vote.proposals',
                         base64.b64encode(candidates.SerializeToString()))
        self._expect_get('sawtooth.config.vote.approval_threshold', '2')

        # the vote should pass
        self._expect_get('my.config.setting')
        self._expect_set('my.config.setting', 'myvalue')

        # expect to update the proposals
        self._expect_get('sawtooth.config.vote.proposals',
                         base64.b64encode(candidates.SerializeToString()))
        self._expect_set('sawtooth.config.vote.proposals',
                         base64.b64encode(EMPTY_CANDIDATES))

        self._expect_ok()

    def test_vote_in_ballot_mode_counted(self):
        """
        Tests voting on a given setting, where the vote is counted only.
        """
        proposal = ConfigProposal(
            setting='my.config.setting',
            value='myvalue',
            nonce='somenonce'
        )
        proposal_id = _to_hash(proposal.SerializeToString())
        record = ConfigCandidate.VoteRecord(
            public_key="some_other_pubkey",
            vote=ConfigVote.ACCEPT)
        candidate = ConfigCandidate(
            proposal_id=proposal_id,
            proposal=proposal,
            votes=[record])

        candidates = ConfigCandidates(candidates=[candidate])

        self._vote(proposal_id, 'my.config.setting', ConfigVote.ACCEPT)

        self._expect_get('sawtooth.config.authorization_type', 'Ballot')
        self._expect_get('sawtooth.config.vote.authorized_keys', '')
        self._expect_get('sawtooth.config.vote.proposals',
                         base64.b64encode(candidates.SerializeToString()))
        self._expect_get('sawtooth.config.vote.approval_threshold', '3')

        # expect to update the proposals
        self._expect_get('sawtooth.config.vote.proposals',
                         base64.b64encode(candidates.SerializeToString()))

        record = ConfigCandidate.VoteRecord(
            public_key="some_other_pubkey",
            vote=ConfigVote.ACCEPT)
        new_record = ConfigCandidate.VoteRecord(
            public_key=self._public_key,
            vote=ConfigVote.ACCEPT)
        candidate = ConfigCandidate(
            proposal_id=proposal_id,
            proposal=proposal,
            votes=[record, new_record])

        updated_candidates = ConfigCandidates(candidates=[candidate])
        self._expect_set(
            'sawtooth.config.vote.proposals',
            base64.b64encode(updated_candidates.SerializeToString()))

        self._expect_ok()

    def test_vote_in_ballot_mode_rejected(self):
        """
        Tests voting on a given setting, where the setting is rejected.
        """
        proposal = ConfigProposal(
            setting='my.config.setting',
            value='myvalue',
            nonce='somenonce'
        )
        proposal_id = _to_hash(proposal.SerializeToString())
        candidate = ConfigCandidate(
            proposal_id=proposal_id,
            proposal=proposal,
            votes=[
                ConfigCandidate.VoteRecord(
                    public_key='some_other_pubkey',
                    vote=ConfigVote.ACCEPT),
                ConfigCandidate.VoteRecord(
                    public_key='a_rejectors_pubkey',
                    vote=ConfigVote.REJECT)
            ])

        candidates = ConfigCandidates(candidates=[candidate])

        self._vote(proposal_id, 'my.config.setting', ConfigVote.REJECT)

        self._expect_get('sawtooth.config.authorization_type', 'Ballot')
        self._expect_get('sawtooth.config.vote.authorized_keys', '')
        self._expect_get('sawtooth.config.vote.proposals',
                         base64.b64encode(candidates.SerializeToString()))
        self._expect_get('sawtooth.config.vote.approval_threshold', '2')

        # expect to update the proposals
        self._expect_get('sawtooth.config.vote.proposals',
                         base64.b64encode(candidates.SerializeToString()))
        self._expect_set('sawtooth.config.vote.proposals',
                         base64.b64encode(EMPTY_CANDIDATES))

        self._expect_ok()

    def test_authorized_keys_accept_no_approval(self):
        """
        Tests setting a value with auth keys and no approval type
        """
        self._propose("foo.bar.count", "1")

        self._expect_get('sawtooth.config.authorization_type', 'None')
        self._expect_get('sawtooth.config.vote.authorized_keys',
                         'some_key,' + self._public_key)

        # check the old value and set the new one
        self._expect_get('foo.bar.count')
        self._expect_set('foo.bar.count', '1')

        self._expect_ok()

    def test_authorized_keys_wrong_key_no_approval(self):
        """
        Tests setting a value with a non-authorized key and no approval type
        """
        self._propose("foo.bar.count", "1")

        self._expect_get('sawtooth.config.authorization_type', 'None')
        self._expect_get('sawtooth.config.vote.authorized_keys',
                         'some_key,some_other_key')

        self._expect_invalid_transaction()

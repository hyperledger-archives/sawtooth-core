
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
import binascii

from sawtooth_config_test.config_message_factory import ConfigMessageFactory
from sawtooth_config.protobuf.config_pb2 import ConfigCandidates
from sawtooth_config.protobuf.config_pb2 import ConfigCandidate
from sawtooth_config.protobuf.config_pb2 import ConfigVote
from sawtooth_config.protobuf.config_pb2 import ConfigProposal


def _to_hash(value):
    return hashlib.sha256(value).hexdigest()


def _get(tst, factory, key, value=None):
    received = tst.expect(
        factory.create_get_request(key))
    tst.respond(
        factory.create_get_response(key, value),
        received)


def _set(tst, factory, key, expected_value):
    received = tst.expect(factory.create_set_request(key, expected_value))
    tst.respond(factory.create_set_response(key), received)


class TestConfig(unittest.TestCase):
    """
    Set of tests to run in a test suite with an existing TPTester and
    transaction processor.
    """

    def __init__(self, test_name, tester):
        super().__init__(test_name)
        self.tester = tester

    def test_set_value_no_auth(self):
        """
        Tests setting a value with no auth and no approvale type
        """
        tst = self.tester
        factory = ConfigMessageFactory()

        tst.send(factory.create_proposal_transaction(
            "foo.bar.count", "1", "somenonce"))

        _get(tst, factory, 'sawtooth.config.authorization_type', 'None')
        _get(tst, factory, 'sawtooth.config.vote.authorized_keys', '')

        # check the old value and set the new one
        _get(tst, factory, 'foo.bar.count')
        _set(tst, factory, 'foo.bar.count', '1')

        tst.expect(factory.create_tp_response("OK"))

    def test_set_value_bad_auth_type(self):
        """
        Tests setting an invalid authorization_type setting
        """
        tst = self.tester
        factory = ConfigMessageFactory()

        tst.send(factory.create_proposal_transaction(
            "sawtooth.config.authorization_type", "foo", "somenonce"))

        _get(tst, factory, 'sawtooth.config.authorization_type', 'None')
        _get(tst, factory, 'sawtooth.config.vote.authorized_keys', '')

        tst.expect(factory.create_tp_response("INVALID_TRANSACTION"))

    def test_set_value_bad_approval_threshold(self):
        """
        Tests setting an invalid approval_threshold.
        """
        tst = self.tester
        factory = ConfigMessageFactory()

        tst.send(factory.create_proposal_transaction(
            "sawtooth.config.vote.approval_threshold", "foo", "somenonce"))

        _get(tst, factory, 'sawtooth.config.authorization_type', 'None')
        _get(tst, factory, 'sawtooth.config.vote.authorized_keys', '')

        tst.expect(factory.create_tp_response("INVALID_TRANSACTION"))

    def test_set_value_proposals(self):
        """
        Tests setting the value of sawtooth.config.vote.proposals, which is
        only an internally set structure.
        """
        tst = self.tester
        factory = ConfigMessageFactory()

        tst.send(factory.create_proposal_transaction(
            'sawtooth.config.vote.proposals',
            ConfigCandidates(candidates={}).SerializeToString(),
            'somenonce'))

        _get(tst, factory, 'sawtooth.config.authorization_type', 'None')
        _get(tst, factory, 'sawtooth.config.vote.authorized_keys', '')

        tst.expect(factory.create_tp_response("INVALID_TRANSACTION"))

    def test_propose_in_ballot_mode(self):
        """
        Tests proposing a value in ballot mode.
        """
        tst = self.tester
        factory = ConfigMessageFactory()

        tst.send(factory.create_proposal_transaction(
            'my.config.setting',
            'myvalue',
            'somenonce'))

        _get(tst, factory, 'sawtooth.config.authorization_type', 'Ballot')
        _get(tst, factory, 'sawtooth.config.vote.authorized_keys', '')
        _get(tst, factory, 'sawtooth.config.vote.approval_threshold', '2')
        _get(tst, factory, 'sawtooth.config.vote.proposals')

        proposal = ConfigProposal(
            setting='my.config.setting',
            value='myvalue',
            nonce='somenonce'
        )
        proposal_id = _to_hash(proposal.SerializeToString())
        candidate = ConfigCandidate(
            proposal=proposal,
            votes={factory.public_key: ConfigVote.ACCEPT})

        candidates = ConfigCandidates(candidates={proposal_id: candidate})

        # Get's again to update the entry
        _get(tst, factory, 'sawtooth.config.vote.proposals')
        _set(tst, factory, 'sawtooth.config.vote.proposals',
             binascii.hexlify(candidates.SerializeToString()))

        tst.expect(factory.create_tp_response("OK"))

    def test_vote_in_ballot_mode_approved(self):
        """
        Tests voting on a given setting, where the setting is approved
        """
        tst = self.tester
        factory = ConfigMessageFactory()

        proposal = ConfigProposal(
            setting='my.config.setting',
            value='myvalue',
            nonce='somenonce'
        )
        proposal_id = _to_hash(proposal.SerializeToString())
        candidate = ConfigCandidate(
            proposal=proposal,
            votes={'some_other_pubkey': ConfigVote.ACCEPT})

        candidates = ConfigCandidates(candidates={proposal_id: candidate})

        tst.send(factory.create_vote_proposal(
            proposal_id, 'my.config.setting', ConfigVote.ACCEPT))

        _get(tst, factory, 'sawtooth.config.authorization_type', 'Ballot')
        _get(tst, factory, 'sawtooth.config.vote.authorized_keys', '')
        _get(tst, factory, 'sawtooth.config.vote.proposals',
             binascii.hexlify(candidates.SerializeToString()))
        _get(tst, factory, 'sawtooth.config.vote.approval_threshold', '2')

        # the vote should pass
        _get(tst, factory, 'my.config.setting')
        _set(tst, factory, 'my.config.setting', 'myvalue')

        # expect to update the proposals
        _get(tst, factory, 'sawtooth.config.vote.proposals',
             binascii.hexlify(candidates.SerializeToString()))
        _set(tst, factory, 'sawtooth.config.vote.proposals',
             binascii.hexlify(
                 ConfigCandidates(candidates={}).SerializeToString()))

        tst.expect(factory.create_tp_response("OK"))

    def test_vote_in_ballot_mode_counted(self):
        """
        Tests voting on a given setting, where the vote is counted only.
        """
        tst = self.tester
        factory = ConfigMessageFactory()

        proposal = ConfigProposal(
            setting='my.config.setting',
            value='myvalue',
            nonce='somenonce'
        )
        proposal_id = _to_hash(proposal.SerializeToString())
        candidate = ConfigCandidate(
            proposal=proposal,
            votes={'some_other_pubkey': ConfigVote.ACCEPT})

        candidates = ConfigCandidates(candidates={proposal_id: candidate})

        tst.send(factory.create_vote_proposal(
            proposal_id, 'my.config.setting', ConfigVote.ACCEPT))

        _get(tst, factory, 'sawtooth.config.authorization_type', 'Ballot')
        _get(tst, factory, 'sawtooth.config.vote.authorized_keys', '')
        _get(tst, factory, 'sawtooth.config.vote.proposals',
             binascii.hexlify(candidates.SerializeToString()))
        _get(tst, factory, 'sawtooth.config.vote.approval_threshold', '3')

        # expect to update the proposals
        _get(tst, factory, 'sawtooth.config.vote.proposals',
             binascii.hexlify(candidates.SerializeToString()))

        candidates.candidates[proposal_id].votes[factory.public_key] = \
            ConfigVote.ACCEPT
        _set(tst, factory, 'sawtooth.config.vote.proposals',
             binascii.hexlify(candidates.SerializeToString()))

        tst.expect(factory.create_tp_response("OK"))

    def test_vote_in_ballot_mode_rejeceted(self):
        """
        Tests voting on a given setting, where the setting is rejected.
        """
        tst = self.tester
        factory = ConfigMessageFactory()

        proposal = ConfigProposal(
            setting='my.config.setting',
            value='myvalue',
            nonce='somenonce'
        )
        proposal_id = _to_hash(proposal.SerializeToString())
        candidate = ConfigCandidate(
            proposal=proposal,
            votes={'some_other_pubkey': ConfigVote.ACCEPT,
                   'a_rejectors_pubkey': ConfigVote.REJECT})

        candidates = ConfigCandidates(candidates={proposal_id: candidate})

        tst.send(factory.create_vote_proposal(
            proposal_id, 'my.config.setting', ConfigVote.REJECT))

        _get(tst, factory, 'sawtooth.config.authorization_type', 'Ballot')
        _get(tst, factory, 'sawtooth.config.vote.authorized_keys', '')
        _get(tst, factory, 'sawtooth.config.vote.proposals',
             binascii.hexlify(candidates.SerializeToString()))
        _get(tst, factory, 'sawtooth.config.vote.approval_threshold', '2')

        # expect to update the proposals
        _get(tst, factory, 'sawtooth.config.vote.proposals',
             binascii.hexlify(candidates.SerializeToString()))
        _set(tst, factory, 'sawtooth.config.vote.proposals',
             binascii.hexlify(
                 ConfigCandidates(candidates={}).SerializeToString()))

        tst.expect(factory.create_tp_response("OK"))

    def test_authorized_keys_accept_no_approval(self):
        """
        Tests setting a value with auth keys and no approval type
        """
        tst = self.tester
        factory = ConfigMessageFactory()

        tst.send(factory.create_proposal_transaction(
            "foo.bar.count", "1", "somenonce"))

        _get(tst, factory, 'sawtooth.config.authorization_type', 'None')
        _get(tst, factory, 'sawtooth.config.vote.authorized_keys',
             'some_key,' + factory.public_key)

        # check the old value and set the new one
        _get(tst, factory, 'foo.bar.count')
        _set(tst, factory, 'foo.bar.count', '1')

        tst.expect(factory.create_tp_response("OK"))

    def test_authorized_keys_wrong_key_no_approval(self):
        """
        Tests setting a value with a non-authorized key and no approval type
        """
        tst = self.tester
        factory = ConfigMessageFactory()

        tst.send(factory.create_proposal_transaction(
            "foo.bar.count", "1", "somenonce"))

        _get(tst, factory, 'sawtooth.config.authorization_type', 'None')
        _get(tst, factory, 'sawtooth.config.vote.authorized_keys',
             'some_key,some_other_key')

        tst.expect(factory.create_tp_response("INVALID_TRANSACTION"))

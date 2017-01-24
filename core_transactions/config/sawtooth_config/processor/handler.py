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
import hashlib
import base64

from sawtooth_sdk.processor.state import StateEntry
from sawtooth_sdk.client.future import FutureTimeoutError
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_protobuf.transaction_pb2 import TransactionHeader

from sawtooth_config.protobuf.config_pb2 import ConfigPayload
from sawtooth_config.protobuf.config_pb2 import ConfigProposal
from sawtooth_config.protobuf.config_pb2 import ConfigVote
from sawtooth_config.protobuf.config_pb2 import ConfigCandidates
from sawtooth_config.protobuf.config_pb2 import SettingEntry

LOGGER = logging.getLogger(__name__)


# The config namespace is special: it is not derived from a hash.
CONFIG_NAMESPACE = '000000'

# Number of seconds to wait for state operations to succeed
STATE_TIMEOUT_SEC = 10


def _to_hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _make_config_key(key):
    return CONFIG_NAMESPACE + _to_hash(key)


def _get_setting_entry(state, address):
    setting_entry = SettingEntry()

    try:
        entries_list = state.get([address], timeout=STATE_TIMEOUT_SEC)
    except FutureTimeoutError:
        LOGGER.warning('Timeout occured on state.get([%s])', address)
        raise InternalError('Unable to get {}'.format(address))

    if len(entries_list) != 0:
        setting_entry.ParseFromString(entries_list[0].data)

    return setting_entry


def _get_config_value(state, key, default_value=None):
    address = _make_config_key(key)
    setting_entry = _get_setting_entry(state, address)
    if key in setting_entry.values:
        return setting_entry.values[key]
    else:
        return default_value


def _set_config_value(state, key, value):
    address = _make_config_key(key)
    setting_entry = _get_setting_entry(state, address)

    old_value = None
    if key in setting_entry.values:
        old_value = setting_entry.values[key]
        del setting_entry.values[key]

    setting_entry.values[key] = value

    try:
        addresses = list(state.set(
            [StateEntry(address=address,
                        data=setting_entry.SerializeToString())],
            timeout=STATE_TIMEOUT_SEC))
    except FutureTimeoutError:
        LOGGER.warning(
            'Timeout occured on state.set([%s, <value>])', address)
        raise InternalError('Unable to set {}'.format(key))

    if len(addresses) != 1:
        LOGGER.warning(
            'Failed to save value on address %s', address)
        raise InternalError(
            'Unable to save config value {}'.format(key))
    LOGGER.info('Config setting %s changed from %s to %s',
                key, old_value, value)


def _get_config_candidates(state):
    value = _get_config_value(state, 'sawtooth.config.vote.proposals')
    if not value:
        return ConfigCandidates(candidates={})
    else:
        config_candidates = ConfigCandidates()
        config_candidates.ParseFromString(base64.b64decode(value))
        return config_candidates


def _save_config_candidates(state, config_candidates):
    _set_config_value(state,
                      'sawtooth.config.vote.proposals',
                      base64.b64encode(config_candidates.SerializeToString()))


def _get_auth_type(state):
    return _get_config_value(state,
                             'sawtooth.config.authorization_type',
                             'None')


def _get_approval_threshold(state):
    return int(_get_config_value(state,
                                 'sawtooth.config.vote.approval_threshold',
                                 1))


def _get_auth_keys(state):
    value = _get_config_value(state,
                              'sawtooth.config.vote.authorized_keys',
                              '')
    return [v.strip() for v in value.split(',') if len(v) > 0]


def _validate_setting(setting, value):
    if setting == 'sawtooth.config.authorization_type':
        if value not in ['Ballot', 'None']:
            raise InvalidTransaction(
                'authorization_type {} is not allowed'.format(value))

    if setting == 'sawtooth.config.vote.approval_threshold':
        try:
            int(value)
        except ValueError:
            raise InvalidTransaction('approval_threshold must be an integer')

    if setting == 'sawtooth.config.vote.proposals':
        raise InvalidTransaction(
            'Setting sawtooth.config.vote.proposals is read-only')


class ConfigurationTransactionHandler(object):

    @property
    def family_name(self):
        return 'sawtooth_config'

    @property
    def family_versions(self):
        return ['1.0']

    @property
    def encodings(self):
        return ['application/protobuf']

    @property
    def namespaces(self):
        return [CONFIG_NAMESPACE]

    def apply(self, transaction, state):

        txn_header = TransactionHeader()
        txn_header.ParseFromString(transaction.header)
        pubkey = txn_header.signer_pubkey

        auth_type = _get_auth_type(state)
        auth_keys = _get_auth_keys(state)
        if len(auth_keys) > 0 and pubkey not in auth_keys:
            raise InvalidTransaction(
                '{} is not authorized to change settings'.format(pubkey))

        config_payload = ConfigPayload()
        config_payload.ParseFromString(transaction.payload)

        if auth_type == 'Ballot':
            return self._apply_ballot_config(pubkey,
                                             config_payload,
                                             state)
        elif auth_type == 'None':
            return self._apply_noauth_config(pubkey,
                                             config_payload,
                                             state)
        else:
            LOGGER.error(
                'auth_type %s should not have been allowed', auth_type)
            raise InternalError(
                'auth_type {} should not have been allowed'.format(auth_type))

    def _apply_ballot_config(self, pubkey, config_payload, state):
        if config_payload.action == ConfigPayload.PROPOSE:
            return self._apply_proposal(pubkey, config_payload.data, state)
        elif config_payload.action == ConfigPayload.VOTE:
            return self._apply_vote(pubkey, config_payload.data, state)
        else:
            raise InvalidTransaction(
                "'action' must be one of {PROPOSE, VOTE} in 'Ballot' mode")

    def _apply_noauth_config(self, pubkey, config_payload, state):
        if config_payload.action == ConfigPayload.PROPOSE:
            config_proposal = ConfigProposal()
            config_proposal.ParseFromString(config_payload.data)

            _validate_setting(config_proposal.setting, config_proposal.value)
            _set_config_value(state,
                              config_proposal.setting,
                              config_proposal.value)
        else:
            raise InvalidTransaction("'action' must be PROPOSE in 'None' mode")

    def _apply_proposal(self, pubkey, config_proposal_data, state):
        config_proposal = ConfigProposal()
        config_proposal.ParseFromString(config_proposal_data)

        proposal_id = hashlib.sha256(config_proposal_data).hexdigest()

        approval_threshold = _get_approval_threshold(state)

        _validate_setting(config_proposal.setting, config_proposal.value)

        if approval_threshold >= 1:
            config_candidates = _get_config_candidates(state)
            if proposal_id in config_candidates.candidates:
                raise InvalidTransaction(
                    'Duplicate proposal for {}'.format(
                        config_proposal.setting))

            candidates = config_candidates.candidates
            candidates[proposal_id].votes[pubkey] = ConfigVote.ACCEPT
            candidates[proposal_id].proposal.setting = config_proposal.setting
            candidates[proposal_id].proposal.value = config_proposal.value
            candidates[proposal_id].proposal.nonce = config_proposal.nonce

            LOGGER.debug('Proposal made to set %s to %s',
                         config_proposal.setting,
                         config_proposal.value)
            _save_config_candidates(state, config_candidates)
        else:
            _set_config_value(state,
                              config_proposal.setting,
                              config_proposal.value)

    def _apply_vote(self, pubkey, config_vote_data, state):
        config_vote = ConfigVote()
        config_vote.ParseFromString(config_vote_data)
        proposal_id = config_vote.proposal_id

        config_candidates = _get_config_candidates(state)
        if proposal_id not in config_candidates.candidates:
            raise InvalidTransaction(
                "Proposal {} does not exist.".format(proposal_id))

        approval_threshold = _get_approval_threshold(state)
        config_candidate = config_candidates.candidates[proposal_id]

        if pubkey in config_candidate.votes:
            raise InvalidTransaction(
                '{} has already voted'.format(pubkey))

        config_candidate.votes[pubkey] = config_vote.vote

        accepted_count = 0
        rejected_count = 0
        for _, vote in config_candidate.votes.items():
            if vote == ConfigVote.ACCEPT:
                accepted_count += 1
            elif vote == ConfigVote.REJECT:
                rejected_count += 1

        if accepted_count >= approval_threshold:
            _set_config_value(state,
                              config_candidate.proposal.setting,
                              config_candidate.proposal.value)
            del config_candidates.candidates[proposal_id]
        elif rejected_count >= approval_threshold:
            LOGGER.debug('Proposal for %s was rejected',
                         config_candidate.proposal.setting)
            del config_candidates.candidates[proposal_id]
        else:
            LOGGER.debug('Vote recorded for %s',
                         config_candidate.proposal.setting)

        _save_config_candidates(state, config_candidates)

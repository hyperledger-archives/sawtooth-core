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
from functools import lru_cache

from sawtooth_sdk.processor.context import StateEntry
from sawtooth_sdk.messaging.future import FutureTimeoutError
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_settings.protobuf.settings_pb2 import SettingsPayload
from sawtooth_settings.protobuf.settings_pb2 import SettingProposal
from sawtooth_settings.protobuf.settings_pb2 import SettingVote
from sawtooth_settings.protobuf.settings_pb2 import SettingCandidate
from sawtooth_settings.protobuf.settings_pb2 import SettingCandidates
from sawtooth_settings.protobuf.setting_pb2 import Setting

LOGGER = logging.getLogger(__name__)


# The config namespace is special: it is not derived from a hash.
SETTINGS_NAMESPACE = '000000'

# Number of seconds to wait for state operations to succeed
STATE_TIMEOUT_SEC = 10


class SettingsTransactionHandler(object):

    @property
    def family_name(self):
        return 'sawtooth_settings'

    @property
    def family_versions(self):
        return ['1.0']

    @property
    def encodings(self):
        return ['application/protobuf']

    @property
    def namespaces(self):
        return [SETTINGS_NAMESPACE]

    def apply(self, transaction, state):

        txn_header = TransactionHeader()
        txn_header.ParseFromString(transaction.header)
        pubkey = txn_header.signer_pubkey

        auth_keys = _get_auth_keys(state)
        if auth_keys and pubkey not in auth_keys:
            raise InvalidTransaction(
                '{} is not authorized to change settings'.format(pubkey))

        settings_payload = SettingsPayload()
        settings_payload.ParseFromString(transaction.payload)

        if settings_payload.action == SettingsPayload.PROPOSE:
            return self._apply_proposal(
                auth_keys, pubkey, settings_payload.data, state)
        elif settings_payload.action == SettingsPayload.VOTE:
            return self._apply_vote(pubkey, settings_payload.data,
                                    auth_keys, state)
        else:
            raise InvalidTransaction(
                "'action' must be one of {PROPOSE, VOTE} in 'Ballot' mode")

    def _apply_proposal(self, auth_keys, pubkey, setting_proposal_data, state):
        setting_proposal = SettingProposal()
        setting_proposal.ParseFromString(setting_proposal_data)

        proposal_id = hashlib.sha256(setting_proposal_data).hexdigest()

        approval_threshold = _get_approval_threshold(state)

        _validate_setting(auth_keys,
                          setting_proposal.setting,
                          setting_proposal.value)

        if approval_threshold > 1:
            setting_candidates = _get_setting_candidates(state)

            existing_candidate = _first(
                setting_candidates.candidates,
                lambda candidate: candidate.proposal_id == proposal_id)

            if existing_candidate is not None:
                raise InvalidTransaction(
                    'Duplicate proposal for {}'.format(
                        setting_proposal.setting))

            record = SettingCandidate.VoteRecord(
                public_key=pubkey,
                vote=SettingVote.ACCEPT)
            setting_candidates.candidates.add(
                proposal_id=proposal_id,
                proposal=setting_proposal,
                votes=[record]
            )

            LOGGER.debug('Proposal made to set %s to %s',
                         setting_proposal.setting,
                         setting_proposal.value)
            _save_setting_candidates(state, setting_candidates)
        else:
            _set_setting_value(state,
                               setting_proposal.setting,
                               setting_proposal.value)

    def _apply_vote(self, pubkey, settings_vote_data, authorized_keys, state):
        settings_vote = SettingVote()
        settings_vote.ParseFromString(settings_vote_data)
        proposal_id = settings_vote.proposal_id

        setting_candidates = _get_setting_candidates(state)
        candidate = _first(
            setting_candidates.candidates,
            lambda candidate: candidate.proposal_id == proposal_id)

        if candidate is None:
            raise InvalidTransaction(
                "Proposal {} does not exist.".format(proposal_id))

        candidate_index = _index_of(setting_candidates.candidates, candidate)

        approval_threshold = _get_approval_threshold(state)

        vote_record = _first(candidate.votes,
                             lambda record: record.public_key == pubkey)
        if vote_record is not None:
            raise InvalidTransaction(
                '{} has already voted'.format(pubkey))

        candidate.votes.add(
            public_key=pubkey,
            vote=settings_vote.vote)

        accepted_count = 0
        rejected_count = 0
        for vote_record in candidate.votes:
            if vote_record.vote == SettingVote.ACCEPT:
                accepted_count += 1
            elif vote_record.vote == SettingVote.REJECT:
                rejected_count += 1

        if accepted_count >= approval_threshold:
            _set_setting_value(state,
                               candidate.proposal.setting,
                               candidate.proposal.value)
            del setting_candidates.candidates[candidate_index]
        elif rejected_count >= approval_threshold or \
                (rejected_count + accepted_count) == len(authorized_keys):
            LOGGER.debug('Proposal for %s was rejected',
                         candidate.proposal.setting)
            del setting_candidates.candidates[candidate_index]
        else:
            LOGGER.debug('Vote recorded for %s',
                         candidate.proposal.setting)

        _save_setting_candidates(state, setting_candidates)


def _get_setting_candidates(state):
    value = _get_setting_value(state, 'sawtooth.settings.vote.proposals')
    if not value:
        return SettingCandidates(candidates={})

    setting_candidates = SettingCandidates()
    setting_candidates.ParseFromString(base64.b64decode(value))
    return setting_candidates


def _save_setting_candidates(state, setting_candidates):
    _set_setting_value(state,
                       'sawtooth.settings.vote.proposals',
                       base64.b64encode(
                           setting_candidates.SerializeToString()))


def _get_approval_threshold(state):
    return int(_get_setting_value(
        state, 'sawtooth.settings.vote.approval_threshold', 1))


def _get_auth_keys(state):
    value = _get_setting_value(
        state, 'sawtooth.settings.vote.authorized_keys', '')
    return _split_ignore_empties(value)


def _split_ignore_empties(value):
    return [v.strip() for v in value.split(',') if v]


def _validate_setting(auth_keys, setting, value):
    if not auth_keys and \
            setting != 'sawtooth.settings.vote.authorized_keys':
        raise InvalidTransaction(
            'Cannot set {} until authorized_keys is set.'.format(setting))

    if setting == 'sawtooth.settings.vote.authorized_keys':
        if not _split_ignore_empties(value):
            raise InvalidTransaction('authorized_keys must not be empty.')

    if setting == 'sawtooth.settings.vote.approval_threshold':
        threshold = None
        try:
            threshold = int(value)
        except ValueError:
            raise InvalidTransaction('approval_threshold must be an integer')

        if threshold > len(auth_keys):
            raise InvalidTransaction(
                'approval_threshold must be less than or equal to number of '
                'authorized_keys')

    if setting == 'sawtooth.settings.vote.proposals':
        raise InvalidTransaction(
            'Setting sawtooth.settings.vote.proposals is read-only')


def _get_setting_value(state, key, default_value=None):
    address = _make_settings_key(key)
    setting = _get_setting_entry(state, address)
    for entry in setting.entries:
        if key == entry.key:
            return entry.value

    return default_value


def _set_setting_value(state, key, value):
    address = _make_settings_key(key)
    setting = _get_setting_entry(state, address)

    old_value = None
    old_entry_index = None
    for i, entry in enumerate(setting.entries):
        if key == entry.key:
            old_value = entry.value
            old_entry_index = i

    if old_entry_index is not None:
        setting.entries[old_entry_index].value = value
    else:
        setting.entries.add(key=key, value=value)

    try:
        addresses = list(state.set(
            [StateEntry(address=address,
                        data=setting.SerializeToString())],
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
    if setting != 'sawtooth.settings.vote.proposals':
        LOGGER.info('Setting setting %s changed from %s to %s',
                    key, old_value, value)


def _get_setting_entry(state, address):
    setting = Setting()

    try:
        entries_list = state.get([address], timeout=STATE_TIMEOUT_SEC)
    except FutureTimeoutError:
        LOGGER.warning('Timeout occured on state.get([%s])', address)
        raise InternalError('Unable to get {}'.format(address))

    if entries_list:
        setting.ParseFromString(entries_list[0].data)

    return setting


def _to_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _first(a_list, pred):
    return next((x for x in a_list if pred(x)), None)


def _index_of(iterable, obj):
    return next((i for i, x in enumerate(iterable) if x == obj), -1)


_MAX_KEY_PARTS = 4
_ADDRESS_PART_SIZE = 16
_EMPTY_PART = _to_hash('')[:_ADDRESS_PART_SIZE]


@lru_cache(maxsize=128)
def _make_settings_key(key):
    # split the key into 4 parts, maximum
    key_parts = key.split('.', maxsplit=_MAX_KEY_PARTS - 1)
    # compute the short hash of each part
    addr_parts = [_to_hash(x)[:_ADDRESS_PART_SIZE] for x in key_parts]
    # pad the parts with the empty hash, if needed
    addr_parts.extend([_EMPTY_PART] * (_MAX_KEY_PARTS - len(addr_parts)))

    return SETTINGS_NAMESPACE + ''.join(addr_parts)

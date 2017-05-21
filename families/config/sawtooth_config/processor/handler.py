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

from sawtooth_sdk.processor.state import StateEntry
from sawtooth_sdk.messaging.future import FutureTimeoutError
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from sawtooth_sdk.processor.exceptions import InternalError
from sawtooth_sdk.protobuf.transaction_pb2 import TransactionHeader

from sawtooth_config.protobuf.config_pb2 import ConfigPayload
from sawtooth_config.protobuf.config_pb2 import ConfigProposal
from sawtooth_config.protobuf.config_pb2 import ConfigVote
from sawtooth_config.protobuf.config_pb2 import ConfigCandidate
from sawtooth_config.protobuf.config_pb2 import ConfigCandidates
from sawtooth_config.protobuf.setting_pb2 import Setting

LOGGER = logging.getLogger(__name__)


# The config namespace is special: it is not derived from a hash.
CONFIG_NAMESPACE = '000000'

# Number of seconds to wait for state operations to succeed
STATE_TIMEOUT_SEC = 10


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

        auth_keys = _get_auth_keys(state)
        if len(auth_keys) > 0 and pubkey not in auth_keys:
            raise InvalidTransaction(
                '{} is not authorized to change settings'.format(pubkey))

        config_payload = ConfigPayload()
        config_payload.ParseFromString(transaction.payload)

        if config_payload.action == ConfigPayload.PROPOSE:
            return self._apply_proposal(
                auth_keys, pubkey, config_payload.data, state)
        elif config_payload.action == ConfigPayload.VOTE:
            return self._apply_vote(pubkey, config_payload.data,
                                    auth_keys, state)
        else:
            raise InvalidTransaction(
                "'action' must be one of {PROPOSE, VOTE} in 'Ballot' mode")

    def _apply_proposal(self, auth_keys, pubkey, config_proposal_data, state):
        config_proposal = ConfigProposal()
        config_proposal.ParseFromString(config_proposal_data)

        proposal_id = hashlib.sha256(config_proposal_data).hexdigest()

        approval_threshold = _get_approval_threshold(state)

        _validate_setting(auth_keys,
                          config_proposal.setting,
                          config_proposal.value)

        if approval_threshold > 1:
            config_candidates = _get_config_candidates(state)

            existing_candidate = _first(
                config_candidates.candidates,
                lambda candidate: candidate.proposal_id == proposal_id)

            if existing_candidate is not None:
                raise InvalidTransaction(
                    'Duplicate proposal for {}'.format(
                        config_proposal.setting))

            record = ConfigCandidate.VoteRecord(
                public_key=pubkey,
                vote=ConfigVote.ACCEPT)
            config_candidates.candidates.add(
                proposal_id=proposal_id,
                proposal=config_proposal,
                votes=[record]
            )

            LOGGER.debug('Proposal made to set %s to %s',
                         config_proposal.setting,
                         config_proposal.value)
            _save_config_candidates(state, config_candidates)
        else:
            _set_config_value(state,
                              config_proposal.setting,
                              config_proposal.value)

    def _apply_vote(self, pubkey, config_vote_data, authorized_keys, state):
        config_vote = ConfigVote()
        config_vote.ParseFromString(config_vote_data)
        proposal_id = config_vote.proposal_id

        config_candidates = _get_config_candidates(state)
        candidate = _first(
            config_candidates.candidates,
            lambda candidate: candidate.proposal_id == proposal_id)

        if candidate is None:
            raise InvalidTransaction(
                "Proposal {} does not exist.".format(proposal_id))

        candidate_index = _index_of(config_candidates.candidates, candidate)

        approval_threshold = _get_approval_threshold(state)

        vote_record = _first(candidate.votes,
                             lambda record: record.public_key == pubkey)
        if vote_record is not None:
            raise InvalidTransaction(
                '{} has already voted'.format(pubkey))

        candidate.votes.add(
            public_key=pubkey,
            vote=config_vote.vote)

        accepted_count = 0
        rejected_count = 0
        for vote_record in candidate.votes:
            if vote_record.vote == ConfigVote.ACCEPT:
                accepted_count += 1
            elif vote_record.vote == ConfigVote.REJECT:
                rejected_count += 1

        if accepted_count >= approval_threshold:
            _set_config_value(state,
                              candidate.proposal.setting,
                              candidate.proposal.value)
            del config_candidates.candidates[candidate_index]
        elif rejected_count >= approval_threshold or \
                (rejected_count + accepted_count) == len(authorized_keys):
            LOGGER.debug('Proposal for %s was rejected',
                         candidate.proposal.setting)
            del config_candidates.candidates[candidate_index]
        else:
            LOGGER.debug('Vote recorded for %s',
                         candidate.proposal.setting)

        _save_config_candidates(state, config_candidates)


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


def _get_approval_threshold(state):
    return int(_get_config_value(
        state, 'sawtooth.config.vote.approval_threshold', 1))


def _get_auth_keys(state):
    value = _get_config_value(
        state, 'sawtooth.config.vote.authorized_keys', '')
    return _split_ignore_empties(value)


def _split_ignore_empties(value):
    return [v.strip() for v in value.split(',') if len(v) > 0]


def _validate_setting(auth_keys, setting, value):
    if len(auth_keys) == 0 and \
            setting != 'sawtooth.config.vote.authorized_keys':
        raise InvalidTransaction(
            'Cannot set {} until authorized_keys is set.'.format(setting))

    if setting == 'sawtooth.config.vote.authorized_keys':
        if len(_split_ignore_empties(value)) == 0:
            raise InvalidTransaction('authorized_keys must not be empty.')

    if setting == 'sawtooth.config.vote.approval_threshold':
        threshold = None
        try:
            threshold = int(value)
        except ValueError:
            raise InvalidTransaction('approval_threshold must be an integer')

        if threshold > len(auth_keys):
            raise InvalidTransaction(
                'approval_threshold must be less than or equal to number of '
                'authorized_keys')

    if setting == 'sawtooth.config.vote.proposals':
        raise InvalidTransaction(
            'Setting sawtooth.config.vote.proposals is read-only')


def _get_config_value(state, key, default_value=None):
    address = _make_config_key(key)
    setting = _get_setting_entry(state, address)
    for entry in setting.entries:
        if key == entry.key:
            return entry.value

    return default_value


def _set_config_value(state, key, value):
    address = _make_config_key(key)
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
    if setting != 'sawtooth.config.vote.proposals':
        LOGGER.info('Config setting %s changed from %s to %s',
                    key, old_value, value)


def _get_setting_entry(state, address):
    setting = Setting()

    try:
        entries_list = state.get([address], timeout=STATE_TIMEOUT_SEC)
    except FutureTimeoutError:
        LOGGER.warning('Timeout occured on state.get([%s])', address)
        raise InternalError('Unable to get {}'.format(address))

    if len(entries_list) != 0:
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
def _make_config_key(key):
    # split the key into 4 parts, maximum
    key_parts = key.split('.', maxsplit=_MAX_KEY_PARTS - 1)
    # compute the short hash of each part
    addr_parts = [_to_hash(x)[:_ADDRESS_PART_SIZE] for x in key_parts]
    # pad the parts with the empty hash, if needed
    addr_parts.extend([_EMPTY_PART] * (_MAX_KEY_PARTS - len(addr_parts)))

    return CONFIG_NAMESPACE + ''.join(addr_parts)

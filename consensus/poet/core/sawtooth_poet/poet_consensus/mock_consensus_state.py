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
from unittest import mock


class MockConsensusState(object):
    """Simulates a Consensus State with
       the following parameters initially set to False
    """

    @staticmethod
    def create_mock_consensus_state(committed_too_late=False,
                                    claimed_block_limit=False,
                                    claiming_too_early=False,
                                    claiming_too_frequently=False):
        new_mock = mock.Mock()
        new_mock.validator_signup_was_committed_too_late.return_value = \
            committed_too_late
        new_mock.validator_has_claimed_block_limit.return_value = \
            claimed_block_limit
        new_mock.validator_is_claiming_too_early.return_value = \
            claiming_too_early
        new_mock.validator_is_claiming_too_frequently.return_value = \
            claiming_too_frequently

        return new_mock

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


class MockStateView(object):
    """Simulates a StateView by wrapping a dictionary of address/bytes pairs.
    """

    def __init__(self, state_dict):
        """Constructs a MockStateView with a dict of address/bytes pairs.

        Args:
            state_dict (dict): Dict of address/byte pairs
        """
        self._state = state_dict

    def get(self, address):
        """See sawtooth_validator.state.state_view.StateView.get"""
        return self._state[address]

    def addresses(self):
        """See sawtooth_validator.state.state_view.StateView.addresses"""
        return self._state.keys()

    def leaves(self, prefix):
        """See sawtooth_validator.state.state_view.StateView.leaves"""
        return {
            address: data
            for address, data in self._state.items()
            if address.startswith(prefix)
        }

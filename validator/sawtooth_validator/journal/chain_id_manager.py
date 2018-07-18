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
import os
import logging
from pathlib import Path
from sawtooth_validator.exceptions import LocalConfigurationError

LOGGER = logging.getLogger(__name__)


class ChainIdManager:
    """
    The ChainIdManager is in charge of of keeping track of the block-chain-id
    stored in the data_dir.
    """

    def __init__(self, data_dir):
        self._data_dir = data_dir

    def save_block_chain_id(self, block_chain_id):
        LOGGER.debug('writing block chain id')
        block_chain_id_file = os.path.join(self._data_dir, 'block-chain-id')
        try:
            with open(block_chain_id_file, 'w') as f:
                f.write(block_chain_id)
        except IOError:
            raise LocalConfigurationError(
                "Unable to write to {}".format(block_chain_id_file))

    def get_block_chain_id(self):
        block_chain_id_file = os.path.join(self._data_dir, 'block-chain-id')
        if not Path(block_chain_id_file).is_file():
            return None

        try:
            with open(block_chain_id_file, 'r') as f:
                block_chain_id = f.read()
                return block_chain_id if block_chain_id else None

        except IOError:
            raise LocalConfigurationError(
                'The block-chain-id file exists, but is unreadable')

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
import logging
import os

from journal.journal_core import Journal
from sawtooth.cli.exceptions import CliException

LOGGER = logging.getLogger(__name__)


def genesis_info_file_name(directory):
    return os.path.join(directory, 'genesis_data.json')


def check_for_chain(data_dir, node_name, store_type):
    block_store = Journal.get_store_file(node_name, 'block', data_dir,
                                         store_type=store_type)
    if os.path.isfile(block_store):
        msg = 'block store: %s exists; ' % block_store
        msg += 'skipping genesis block creation.'
        raise CliException(msg)

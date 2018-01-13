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
import time
from urllib.parse import urlparse, parse_qs

from sawtooth_cli.rest_client import RestClient
from sawtooth_cli.exceptions import CliException
from sawtooth_cli.exceptions import RestClientException
from sawtooth_intkey.intkey_message_factory import IntkeyMessageFactory

LOGGER = logging.getLogger(__name__)


class IntkeyClient(RestClient):
    def __init__(self, url, wait=30):
        super().__init__(url)
        self.url = url
        self.factory = IntkeyMessageFactory()
        self.wait = wait

    def send_txns(self, txns):
        batch = self.factory.create_batch(txns)

        attempts = 0
        response = None
        while True:
            try:
                response = self.send_batches(batch)
                id_query = urlparse(response['link']).query
                return parse_qs(id_query)['id'][0]
            except CliException:
                if attempts < 8:
                    LOGGER.info('responding to back-pressure, retrying...')
                    attempts += 1
                    time.sleep(0.2 * (2 ** attempts))
                else:
                    raise

    def recent_block_signatures(self, tolerance):
        return self.list_block_signatures()[:tolerance]

    def list_block_signatures(self):
        return [block['header_signature'] for block in self.list_blocks()]

    def calculate_tolerance(self):
        length = len(list(self.list_blocks()))
        # the most recent nth of the chain, at least 2 blocks
        return max(2, length // 5)

    def poll_for_batches(self, batch_ids):
        """Poll timeout seconds for a batch status to become
           non-pending

        Args:
            batch_id (str): The id to get the status of
        """
        time_waited = 0
        start_time = time.time()

        while time_waited < self.wait:

            res = self._get(
                '/batch_statuses',
                id=','.join(batch_ids),
                wait=(self.wait - time_waited))

            if 'PENDING' not in [data['status'] for data in res['data']]:
                return

            time_waited = time.time() - start_time

        raise RestClientException(
            'Request timed out after %d seconds' % self.wait)

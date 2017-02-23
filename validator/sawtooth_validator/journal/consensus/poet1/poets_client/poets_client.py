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

from collections import OrderedDict
from urllib.parse import urljoin
import logging
import requests


LOGGER = logging.getLogger(__name__)


def ascii_encode_dict(item):
    """
    Support method to ensure that JSON is converted to ascii since unicode
    identifiers, in particular, can cause problems
    """
    if isinstance(item, dict):
        return OrderedDict(
            (ascii_encode_dict(key), ascii_encode_dict(item[key]))
            for key in sorted(item.keys()))
    elif isinstance(item, list):
        return [ascii_encode_dict(element) for element in item]
    elif isinstance(item, str):
        return item.encode('ascii')
    else:
        return item


class PoetsClient(object):
    """
    Reference Client for PoET as a Service(PoETS) Server.

    _poet_server_url: ServerUrl
    _proxies: HttpsProxy
    _client_cert: ClientCert
    _client_key: ClientKey
    _server_cert: ServerCert
    """
    def __init__(self, **kwargs):
        self._poet_server_url = kwargs["PoetsServerUrl"]
        self._proxies = {}
        if "HttpsProxy" in kwargs:
            self._proxies["https"] = kwargs["PoetsHttpsProxy"]

    def _post_request(self, path, json):

        url = urljoin(self._poet_server_url, path)
        result = requests.post(url,
                               json=json,
                               proxies=self._proxies)
        return result

    def create_wait_timer(
            self,
            validator_address,
            previous_certificate_id,
            local_mean):
        """
        Calls the Poets Server to generate a create a WaitTimer
        """
        json = {
            "ValidatorAddress": validator_address,
            "PreviousCertID": previous_certificate_id,
            "LocalMean": local_mean
        }
        result = self._post_request("v1/CreateWaitTimer", json)
        if result.status_code != requests.codes.created:
            LOGGER.error("CreateWaitTimer HTTP Error code : %d",
                         result.status_code)
            result.raise_for_status()
        return ascii_encode_dict(result.json())

    def create_wait_certificate(self, waittimer, block_hash):
        """
        Calls the Poets Server to create a WaitCertificate
        """
        json = {
            "WaitTimer": waittimer,
            "BlockHash": block_hash,
        }
        result = self._post_request("v1/CreateWaitCertificate", json)
        if result.status_code != requests.codes.created:
            LOGGER.error(
                "CreateWaitCertificate HTTP Error code : %d",
                result.status_code)
            return None

        return ascii_encode_dict(result.json())

    def verify_wait_certificate(self, wait_certificate):
        """
        Calls the Poets Server to verify a WaitCertificate
        """
        json = {
            "WaitCertificate": wait_certificate,
        }
        result = self._post_request("v1/VerifyWaitCertificate", json)
        if result.status_code != requests.codes.ok:
            LOGGER.error(
                "VerifyWaitCertificate HTTP Error code : %d",
                result.status_code)
            result.raise_for_status()
            return False
        return True

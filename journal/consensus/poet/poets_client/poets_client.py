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
from urlparse import urljoin

import requests

from gossip.common import ascii_encode_dict

logger = logging.getLogger(__name__)


"""
Reference Client for PoET as a Service(PoETS) Server.
"""


class PoetsClient(object):
    """
    Reference Poets Client

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
        self._client_cert = kwargs["PoetsClientCert"]
        if not os.path.exists(self._client_cert):
            raise IOError("ClientCert not found: {}".format(self._client_cert))

        self._client_key = kwargs["PoetsClientKey"]
        if not os.path.exists(self._client_key):
            raise IOError("ClientKey not found: {}".format(self._client_key))

        self._server_cert = kwargs["PoetsServerCert"]
        if not os.path.exists(self._server_cert):
            raise IOError("ServerCert not found: {}".format(self._server_cert))

    def _post_request(self, path, json):

        url = urljoin(self._poet_server_url, path)
        result = requests.post(
            url,
            json=json,
            # proxies=self._proxies,
            cert=(self._client_cert, self._client_key),
            verify=self._server_cert)
        return result

    def create_wait_timer(self, previous_certificate_id, local_mean):
        """
        Calls the Poets Server to generate a create a WaitTimer
        """
        json = {"PreviousCertID": previous_certificate_id,
                "LocalMean": local_mean}
        result = self._post_request("CreateWaitTimer", json)
        if result.status_code != requests.codes.created:
            logger.error("/CreateWaitTimer HTTP Error code : %d",
                         result.status_code)
            result.raise_for_status()
        return ascii_encode_dict(result.json())

    def create_wait_certificate(self, waittimer):
        """
        Calls the Poets Server to create a WaitCertificate
        """
        json = {
            "WaitTimer": waittimer,
        }
        result = self._post_request("CreateWaitCertificate", json)
        if result.status_code != requests.codes.created:
            logger.error(
                "/CreateWaitCertificate HTTP Error code : %d",
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
        result = self._post_request("VerifyWaitCertificate", json)
        if result.status_code != requests.codes.ok:
            logger.error(
                "/VerifyWaitCertificate HTTP Error code : %d",
                result.status_code)
            result.raise_for_status()
            return False
        return True

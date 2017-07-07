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

"""
Provide rest api helper functions for communicating with IAS.
"""

import logging
from urllib.parse import urljoin

import requests

LOGGER = logging.getLogger(__name__)


class IasClient(object):
    """
    Provide rest api helper functions for communicating with IAS.
    """

    def __init__(self, ias_url, spid_cert_file, timeout=300):
        self._ias_url = ias_url
        self._cert = spid_cert_file
        self._timeout = timeout

    def get_signature_revocation_lists(self,
                                       gid='',
                                       path='/attestation/sgx/v2/sigrl'):
        """
        @param gid: Hex, base16 encoded
        @param path: URL path for sigrl request
        @return: Base 64-encoded SigRL for EPID
                group identified by {gid} parameter.
        """

        path = '{}/{}'.format(path, gid) if gid else path
        url = urljoin(self._ias_url, path)
        LOGGER.debug("Fetching SigRL from: %s", url)
        result = requests.get(url, cert=self._cert, timeout=self._timeout)
        if result.status_code != requests.codes.ok:
            LOGGER.error("get_signature_revocation_lists HTTP Error code : %d",
                         result.status_code)
            result.raise_for_status()
        # Convert unicode to ascii
        return str(result.text)

    def post_verify_attestation(self, quote, manifest=None, nonce=None):
        """
        @param quote: base64 encoded quote attestation
        @return: A dictionary containing the following:
            'attestation_verification_report': The body (JSON) of the
                response from ISA.
            'signature': The base 64-encoded RSA-SHA256 signature of the
                response body (aka, AVR) using the report key.  Will be None
                if the header does not contain a signature.
        """

        path = '/attestation/sgx/v2/report'
        url = urljoin(self._ias_url, path)
        LOGGER.debug("Posting attestation verification request to: %s",
                     url)
        json = {"isvEnclaveQuote": quote}

        if manifest is not None:
            json['pseManifest'] = manifest
        if nonce is not None:
            json['nonce'] = nonce

        LOGGER.debug("Posting attestation evidence payload: %s", json)

        response = requests.post(url, json=json, cert=self._cert,
                                 timeout=self._timeout)
        LOGGER.debug("received attestation result code: %d",
                     response.status_code)
        if response.status_code != requests.codes.ok:
            LOGGER.error("post_verify_attestation HTTP Error code : %d",
                         response.status_code)
            response.raise_for_status()
        LOGGER.debug("received attestation result: %s",
                     response.json())

        result = {
            'verification_report': response.text,
            'signature': response.headers.get('x-iasreport-signature')
        }

        return result

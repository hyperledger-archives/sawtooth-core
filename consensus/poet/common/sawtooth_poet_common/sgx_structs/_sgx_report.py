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

import struct

from sawtooth_poet_common.sgx_structs._sgx_struct import SgxStruct
from sawtooth_poet_common.sgx_structs._sgx_report_body import SgxReportBody
from sawtooth_poet_common.sgx_structs._sgx_key_id import SgxKeyId


class SgxReport(SgxStruct):
    """
    Provide a wrapper around sgx_report_t structure

    #define SGX_MAC_SIZE 16
    typedef uint8_t sgx_mac_t[SGX_MAC_SIZE];

    typedef struct _report_t
    {
        sgx_report_body_t   body;   /* 0   */
        sgx_key_id_t        key_id; /* 384 */
        sgx_mac_t           mac;    /* 416 */
    } sgx_report_t;

    See: https://01.org/sites/default/files/documentation/
                intel_sgx_sdk_developer_reference_for_linux_os_pdf.pdf
    """

    STRUCT_SIZE = 432

    _DEFAULT_MAC = b'\x00' * 16

    _format = \
        '<{}s{}s{}s'.format(
            SgxReportBody.STRUCT_SIZE,
            SgxKeyId.STRUCT_SIZE,
            len(_DEFAULT_MAC))

    def __init__(self,
                 body=SgxReportBody(),
                 key_id=SgxKeyId(),
                 mac=_DEFAULT_MAC):
        """Initialize SgxReport object

        Args:
            body (SgxReportBody): Information about the enclave
            key_id (SgxKeyId): Value for the key wear-out protection
            mac (bytes): The CMAC value of the report data
        """
        self.body = body
        self.key_id = key_id
        self.mac = mac

    def __str__(self):
        return \
            'SGX_REPORT: body={{{}}}, key_id={{{}}}, mac={}'.format(
                self.body,
                self.key_id,
                self.mac.hex())

    def serialize_to_bytes(self):
        """Serializes a object representing an SGX structure to bytes
        laid out in its corresponding C/C++ format.

        NOTE: All integer struct fields are serialized to little endian
            format

        Returns:
            bytes: The C/C++ representation of the object as a struct
        """
        return \
            struct.pack(
                self._format,
                self.body.serialize_to_bytes(),
                self.key_id.serialize_to_bytes(),
                self.mac)

    def parse_from_bytes(self, raw_buffer):
        """Parses a byte array and creates the Sgx* object corresponding
        to the C/C++ struct.

        NOTE: All integer struct fields are parsed as little endian
            format

        Args:
            raw_buffer (bytes): A byte array representing the corresponding
                C/C++ struct used to parse into the object

        Returns:
            None

        Raises:
            TypeError: raw_buffer is not a byte array (aka, bytes)
            ValueError: raw_buffer is not a valid C/C++ struct layout
        """

        try:
            (body, key_id, self.mac) = struct.unpack(self._format, raw_buffer)

            # Further parse embedded structures
            self.body.parse_from_bytes(body)
            self.key_id.parse_from_bytes(key_id)
        except struct.error as se:
            raise ValueError('Unable to parse: {}'.format(se))

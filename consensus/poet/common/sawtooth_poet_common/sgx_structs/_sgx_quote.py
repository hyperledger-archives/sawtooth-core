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
from sawtooth_poet_common.sgx_structs._sgx_basename import SgxBasename
from sawtooth_poet_common.sgx_structs._sgx_report_body import SgxReportBody


class SgxQuote(SgxStruct):
    """
    Provide a wrapper around sgx_quote_t structure

    typedef uint8_t sgx_epid_group_id_t[4];
    typedef uint16_t sgx_isv_svn_t;

    typedef struct _quote_t
    {
        uint16_t            version;                /* 0   */
        uint16_t            sign_type;              /* 2   */
        sgx_epid_group_id_t epid_group_id;          /* 4   */
        sgx_isv_svn_t       qe_svn;                 /* 8   */
        sgx_isv_svn_t       pce_svn;                /* 10  */
        uint32_t            extended_epid_group_id; /* 12  */
        sgx_basename_t      basename;               /* 16  */
        sgx_report_body_t   report_body;            /* 48  */
        uint32_t            signature_len;          /* 432 */
        uint8_t             signature[];            /* 436 */
    } sgx_quote_t;

    See: https://01.org/sites/default/files/documentation/
                intel_sgx_sdk_developer_reference_for_linux_os_pdf.pdf
    """
    FIXED_STRUCT_SIZE = 432

    _DEFAULT_EPID_GROUP_ID = b'\x00' * 4
    _DEFAULT_SIGNATURE = b''

    _fixed_format = \
        '<HH4sHHL{0}s{1}s'.format(
            SgxBasename.STRUCT_SIZE,
            SgxReportBody.STRUCT_SIZE)
    _variable_format = '<L{}s'

    def __init__(self,
                 version=0,
                 sign_type=0,
                 epid_group_id=_DEFAULT_EPID_GROUP_ID,
                 qe_svn=0,
                 pce_svn=0,
                 extended_epid_group_id=0,
                 basename=SgxBasename(),
                 report_body=SgxReportBody(),
                 signature_len=0,
                 signature=_DEFAULT_SIGNATURE):
        """Initialize SgxQuote object

        Args:
            version (int): The version of the quote structure
            sign_type (int): The EPID signature type
                0 - Unlinkable signature
                1 - Linkable signature
            epid_group_id (bytes): The EPID group id of the platform
            qe_svn (int): The quoting enclave security version
            pce_svn (int): The provisioning certification enclave security
                version
            extended_epid_group_id (int): The extended EPID group ID
            basename (SgxBasename): The basename used in the enclave quote
            report_body (SgxReportBody): The report body of the application
                enclave
            signature_len (int): The size, in bytes, of the signature
            signature(bytes): The signature
        """
        self.version = version
        self.sign_type = sign_type
        self.epid_group_id = epid_group_id
        self.qe_svn = qe_svn
        self.pce_svn = pce_svn
        self.extended_epid_group_id = extended_epid_group_id
        self.basename = basename
        self.report_body = report_body
        self.signature_len = signature_len
        self.signature = signature

    def __str__(self):
        return \
            'SGX_QUOTE: version={}, sign_type={}, epid_group_id={}, '\
            'qe_svn={}, pce_svn={}, extended_epid_group_id={}, '\
            'basename={{{}}}, report_body={{{}}}, signature_len={}, '\
            'signature={}'.format(
                self.version,
                self.sign_type,
                self.epid_group_id.hex(),
                self.qe_svn,
                self.pce_svn,
                self.extended_epid_group_id,
                self.basename,
                self.report_body,
                self.signature_len,
                self.signature.hex())

    def serialize_to_bytes(self):
        """Serializes a object representing an SGX structure to bytes
        laid out in its corresponding C/C++ format.

        NOTE: All integer struct fields are serialized to little endian
            format

        Returns:
            bytes: The C/C++ representation of the object as a struct
        """
        fixed_bytes = \
            struct.pack(
                self._fixed_format,
                self.version,
                self.sign_type,
                self.epid_group_id,
                self.qe_svn,
                self.pce_svn,
                self.extended_epid_group_id,
                self.basename.serialize_to_bytes(),
                self.report_body.serialize_to_bytes())
        variable_bytes =\
            struct.pack(
                self._variable_format.format(self.signature_len),
                self.signature_len,
                self.signature)
        return fixed_bytes + variable_bytes

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
            # First unpack the fixed portion of the structure
            (self.version,
             self.sign_type,
             self.epid_group_id,
             self.qe_svn,
             self.pce_svn,
             self.extended_epid_group_id,
             basename,
             report_body) = \
                struct.unpack(
                    '<HH4sHHL{0}s{1}s'.format(
                        SgxBasename.STRUCT_SIZE,
                        SgxReportBody.STRUCT_SIZE),
                    raw_buffer[:self.FIXED_STRUCT_SIZE])

            # Further parse embedded structures
            self.basename.parse_from_bytes(basename)
            self.report_body.parse_from_bytes(report_body)

            # Set default values for signature
            self.signature_len = 0
            self.signature = self._DEFAULT_SIGNATURE

            # It appears from empirical testing that if there is no signature
            # then in some cases, specifically when receiving a quote from
            # IAS, the signature length field appears to not be included.
            if len(raw_buffer) > self.FIXED_STRUCT_SIZE:
                (self.signature_len,) = \
                    struct.unpack(
                        '<L',
                        raw_buffer[
                            self.FIXED_STRUCT_SIZE:
                            self.FIXED_STRUCT_SIZE + 4])

                # If the signature length is non-zero, then the rest of the
                # buffer is the signature.  We are still going to use
                # struct.unpack in order to verify the length, etc.
                if self.signature_len != 0:
                    (self.signature,) = \
                        struct.unpack(
                            '<{}s'.format(self.signature_len),
                            raw_buffer[self.FIXED_STRUCT_SIZE + 4:])
        except struct.error as se:
            raise ValueError('Unable to parse: {}'.format(se))

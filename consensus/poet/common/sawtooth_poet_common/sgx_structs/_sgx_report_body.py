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
from sawtooth_poet_common.sgx_structs._sgx_cpu_svn import SgxCpuSvn
from sawtooth_poet_common.sgx_structs._sgx_attributes import SgxAttributes
from sawtooth_poet_common.sgx_structs._sgx_measurement import SgxMeasurement
from sawtooth_poet_common.sgx_structs._sgx_report_data import SgxReportData


class SgxReportBody(SgxStruct):
    """
    Provide a wrapper around sgx_report_body_t structure

    typedef uint32_t sgx_misc_select_t;
    typedef uint16_t sgx_prod_id_t;
    typedef uint16_t sgx_isv_svn_t;

    typedef struct _report_body_t
    {
        sgx_cpu_svn_t           cpu_svn;        /* 0   */
        sgx_misc_select_t       misc_select;    /* 16  */
        uint8_t                 reserved1[28];  /* 20  */
        sgx_attributes_t        attributes;     /* 48  */
        sgx_measurement_t       mr_enclave;     /* 64  */
        uint8_t                 reserved2[32];  /* 96  */
        sgx_measurement_t       mr_signer;      /* 128 */
        uint8_t                 reserved3[96];  /* 160 */
        sgx_prod_id_t           isv_prod_id;    /* 256 */
        sgx_isv_svn_t           isv_svn;        /* 258 */
        uint8_t                 reserved4[60];  /* 260 */
        sgx_report_data_t       report_data;    /* 320 */
    } sgx_report_body_t;

    See: https://01.org/sites/default/files/documentation/
                intel_sgx_sdk_developer_reference_for_linux_os_pdf.pdf
    """

    STRUCT_SIZE = 384

    _RESERVED_1 = b'\x00' * 28
    _RESERVED_2 = b'\x00' * 32
    _RESERVED_3 = b'\x00' * 96
    _RESERVED_4 = b'\x00' * 60

    _format = \
        '<{0}sL28s{1}s{2}s32s{2}s96sHH60s{3}s'.format(
            SgxCpuSvn.STRUCT_SIZE,
            SgxAttributes.STRUCT_SIZE,
            SgxMeasurement.STRUCT_SIZE,
            SgxReportData.STRUCT_SIZE)

    def __init__(self,
                 cpu_svn=SgxCpuSvn(),
                 misc_select=0,
                 attributes=SgxAttributes(),
                 mr_enclave=SgxMeasurement(),
                 mr_signer=SgxMeasurement(),
                 isv_prod_id=0,
                 isv_svn=0,
                 report_data=SgxReportData()):
        """Initialize SgxReportBody object

        Args:
            cpu_svn (SgxCpuSvn): Security version number of host system CPU
            misc_select (int): The miscellaneous select bits for the enclave
            attributes (SgxAttributes): The attributes for the enclave
            mr_enclave (SgxMeasurement): The measurement value of the enclave
            mr_signer (SgxMeasurement): The measurement value of the public
                key that verified the enclave
            isv_prod_id (int): The ISV product ID of the enclave
            isv_svn (int): The ISV security version number of the enclave
            report_data (SgxReportData):
        """
        self.cpu_svn = cpu_svn
        self.misc_select = misc_select
        self.attributes = attributes
        self.mr_enclave = mr_enclave
        self.mr_signer = mr_signer
        self.isv_prod_id = isv_prod_id
        self.isv_svn = isv_svn
        self.report_data = report_data

    def __str__(self):
        return \
            'SGX_REPORT_BODY: cpu_svn={{{}}}, misc_select={}, ' \
            'attributes={{{}}}, mr_enclave={{{}}}, mr_signer={{{}}}, ' \
            'isv_prod_id={}, isv_svn={}, report_data={{{}}}'.format(
                self.cpu_svn,
                self.misc_select,
                self.attributes,
                self.mr_enclave,
                self.mr_signer,
                self.isv_prod_id,
                self.isv_svn,
                self.report_data)

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
                self.cpu_svn.serialize_to_bytes(),
                self.misc_select,
                self._RESERVED_1,
                self.attributes.serialize_to_bytes(),
                self.mr_enclave.serialize_to_bytes(),
                self._RESERVED_2,
                self.mr_signer.serialize_to_bytes(),
                self._RESERVED_3,
                self.isv_prod_id,
                self.isv_svn,
                self._RESERVED_4,
                self.report_data.serialize_to_bytes())

    def parse_from_bytes(self, raw_buffer):
        """Parses a byte array and creates the Sgx* object corresponding
        to the C/C++ struct.

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
            (cpu_svn,
             self.misc_select,
             _,
             attributes,
             mr_enclave,
             _,
             mr_signer,
             _,
             self.isv_prod_id,
             self.isv_svn,
             _,
             report_data) = \
                struct.unpack(self._format, raw_buffer)

            # Further parse embedded structures
            self.cpu_svn.parse_from_bytes(cpu_svn)
            self.attributes.parse_from_bytes(attributes)
            self.mr_enclave.parse_from_bytes(mr_enclave)
            self.mr_signer.parse_from_bytes(mr_signer)
            self.report_data.parse_from_bytes(report_data)
        except struct.error as se:
            raise ValueError('Unable to parse: {}'.format(se))

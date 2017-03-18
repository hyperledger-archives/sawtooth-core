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


class SgxCpuSvn(SgxStruct):
    """
    Provide a wrapper around sgx_cpu_svn_t

    #define SGX_CPUSVN_SIZE 16

    typedef struct _sgx_cpu_svn_t
    {
        uint8_t svn[SGX_CPUSVN_SIZE];
    } sgx_cpu_svn_t;

    See: https://01.org/sites/default/files/documentation/
                intel_sgx_sdk_developer_reference_for_linux_os_pdf.pdf
    """

    STRUCT_SIZE = 16

    _DEFAULT_SVN = b'\x00' * STRUCT_SIZE

    _format = '<{}s'.format(STRUCT_SIZE)

    def __init__(self, svn=_DEFAULT_SVN):
        """Initialize SgxCpuSvn object

        Args:
            svn (bytes): CPU security version
        """

        self.svn = svn

    def __str__(self):
        return 'SGX_CPU_SVN: svn={}'.format(self.svn.hex())

    def serialize_to_bytes(self):
        """Serializes a object representing an SGX structure to bytes
        laid out in its corresponding C/C++ format.

        NOTE: If len(self.svn) is less than self.STRUCT_SIZE, the
            resulting bytes will be padded with binary zero (\x00).  If
            len(self.svn) is greater than self.STRUCT_SIZE, the
            resulting bytes will be truncated to self.STRUCT_SIZE.

        Returns:
            bytes: The C/C++ representation of the object as a struct
        """
        return struct.pack(self._format, self.svn)

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
            (self.svn,) = struct.unpack(self._format, raw_buffer)
        except struct.error as se:
            raise ValueError('Unable to parse: {}'.format(se))

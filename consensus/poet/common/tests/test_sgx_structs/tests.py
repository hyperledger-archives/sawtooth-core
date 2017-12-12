#!/usr/bin/env python
#
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

import unittest
import struct
import os

from sawtooth_poet_common import sgx_structs

# NOTE - all of the tests below that unpack a buffer into an integer (16-, 32-,
# or 64-bit) assume that the unsigned integer is in little endian (i.e., if the
# buffer is '00112233', the integer value is actually 0x33221100) as these
# structures are meant to be used with data being returned from IAS and in
# their documentation, all integers in structures are assumed to be laid out as
# little endian.


class TestSgxStructs(unittest.TestCase):
    @staticmethod
    def create_random_buffer(length):
        return os.urandom(length)

    def test_sgx_cpu_svn(self):
        sgx_cpu_svn = sgx_structs.SgxCpuSvn()

        # Test with None and invalid types
        with self.assertRaises(TypeError):
            sgx_cpu_svn.parse_from_bytes(None)
        with self.assertRaises(TypeError):
            sgx_cpu_svn.parse_from_bytes([])
        with self.assertRaises(TypeError):
            sgx_cpu_svn.parse_from_bytes({})
        with self.assertRaises(TypeError):
            sgx_cpu_svn.parse_from_bytes(1)
        with self.assertRaises(TypeError):
            sgx_cpu_svn.parse_from_bytes(1.0)
        with self.assertRaises(TypeError):
            sgx_cpu_svn.parse_from_bytes('')

        # Test an empty string, a string that is one too short, and a string
        # that is one too long
        with self.assertRaises(ValueError):
            sgx_cpu_svn.parse_from_bytes(b'')
        with self.assertRaises(ValueError):
            sgx_cpu_svn.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxCpuSvn.STRUCT_SIZE - 1))
        with self.assertRaises(ValueError):
            sgx_cpu_svn.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxCpuSvn.STRUCT_SIZE + 1))

        # Verify sgx_cpu_svn unpacks properly
        cpu_svn = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxCpuSvn.STRUCT_SIZE)

        sgx_cpu_svn.parse_from_bytes(cpu_svn)
        self.assertTrue(sgx_cpu_svn.svn == cpu_svn)

        # Reset the object using the field values and verify that we
        # get expected serialized buffer
        sgx_cpu_svn = sgx_structs.SgxCpuSvn(svn=cpu_svn)
        self.assertEqual(cpu_svn, sgx_cpu_svn.serialize_to_bytes())

    def test_sgx_attributes(self):
        sgx_attributes = sgx_structs.SgxAttributes()

        # Test with None and invalid types
        with self.assertRaises(TypeError):
            sgx_attributes.parse_from_bytes(None)
        with self.assertRaises(TypeError):
            sgx_attributes.parse_from_bytes([])
        with self.assertRaises(TypeError):
            sgx_attributes.parse_from_bytes({})
        with self.assertRaises(TypeError):
            sgx_attributes.parse_from_bytes(1)
        with self.assertRaises(TypeError):
            sgx_attributes.parse_from_bytes(1.0)
        with self.assertRaises(TypeError):
            sgx_attributes.parse_from_bytes('')

        # Test an empty string, a string that is one too short, and a string
        # that is one too long
        with self.assertRaises(ValueError):
            sgx_attributes.parse_from_bytes(b'')
        with self.assertRaises(ValueError):
            sgx_attributes.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxAttributes.STRUCT_SIZE - 1))
        with self.assertRaises(ValueError):
            sgx_attributes.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxAttributes.STRUCT_SIZE + 1))

        # Simply verify that buffer of correct size unpacks without error
        sgx_attributes.parse_from_bytes(
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxAttributes.STRUCT_SIZE))

        # Verify sgx_attributes unpacks properly.
        flags = 0x0001020304050607
        xfrm = 0x08090a0b0c0d0e0f
        attributes = struct.pack(b'<QQ', flags, xfrm)
        sgx_attributes.parse_from_bytes(attributes)

        self.assertTrue(sgx_attributes.flags == flags)
        self.assertTrue(sgx_attributes.xfrm == xfrm)

        # Reset the object using the field values and verify that we
        # get expected serialized buffer
        sgx_attributes = sgx_structs.SgxAttributes(flags=flags, xfrm=xfrm)
        self.assertEqual(attributes, sgx_attributes.serialize_to_bytes())

    def test_sgx_measurement(self):
        sgx_measurement = sgx_structs.SgxMeasurement()

        # Test with None and invalid types
        with self.assertRaises(TypeError):
            sgx_measurement.parse_from_bytes(None)
        with self.assertRaises(TypeError):
            sgx_measurement.parse_from_bytes([])
        with self.assertRaises(TypeError):
            sgx_measurement.parse_from_bytes({})
        with self.assertRaises(TypeError):
            sgx_measurement.parse_from_bytes(1)
        with self.assertRaises(TypeError):
            sgx_measurement.parse_from_bytes(1.0)
        with self.assertRaises(TypeError):
            sgx_measurement.parse_from_bytes('')

        # Test an empty string, a string that is one too short, and a string
        # that is one too long
        with self.assertRaises(ValueError):
            sgx_measurement.parse_from_bytes(b'')
        with self.assertRaises(ValueError):
            sgx_measurement.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxMeasurement.STRUCT_SIZE - 1))
        with self.assertRaises(ValueError):
            sgx_measurement.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxMeasurement.STRUCT_SIZE + 1))

        # Verify sgx_measurement unpacks properly
        measurement = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxMeasurement.STRUCT_SIZE)
        sgx_measurement.parse_from_bytes(measurement)

        self.assertTrue(sgx_measurement.m == measurement)

        # Reset the object using the field values and verify that we
        # get expected serialized buffer
        sgx_measurement = sgx_structs.SgxMeasurement(m=measurement)
        self.assertEqual(measurement, sgx_measurement.serialize_to_bytes())

    def test_sgx_report_data(self):
        sgx_report_data = sgx_structs.SgxReportData()

        # Test with None and invalid types
        with self.assertRaises(TypeError):
            sgx_report_data.parse_from_bytes(None)
        with self.assertRaises(TypeError):
            sgx_report_data.parse_from_bytes([])
        with self.assertRaises(TypeError):
            sgx_report_data.parse_from_bytes({})
        with self.assertRaises(TypeError):
            sgx_report_data.parse_from_bytes(1)
        with self.assertRaises(TypeError):
            sgx_report_data.parse_from_bytes(1.0)
        with self.assertRaises(TypeError):
            sgx_report_data.parse_from_bytes('')

        # Test an empty string, a string that is one too short, and a string
        # that is one too long
        with self.assertRaises(ValueError):
            sgx_report_data.parse_from_bytes(b'')
        with self.assertRaises(ValueError):
            sgx_report_data.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxReportData.STRUCT_SIZE - 1))
        with self.assertRaises(ValueError):
            sgx_report_data.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxReportData.STRUCT_SIZE + 1))

        # Verify sgx_report_data unpacks properly
        report_data = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxReportData.STRUCT_SIZE)
        sgx_report_data.parse_from_bytes(report_data)

        self.assertTrue(sgx_report_data.d == report_data)

        # Reset the object using the field values and verify that we
        # get expected serialized buffer
        sgx_report_data = sgx_structs.SgxReportData(d=report_data)
        self.assertEqual(report_data, sgx_report_data.serialize_to_bytes())

    def test_sgx_report_body(self):
        sgx_report_body = sgx_structs.SgxReportBody()

        # Test with None and invalid types
        with self.assertRaises(TypeError):
            sgx_report_body.parse_from_bytes(None)
        with self.assertRaises(TypeError):
            sgx_report_body.parse_from_bytes([])
        with self.assertRaises(TypeError):
            sgx_report_body.parse_from_bytes({})
        with self.assertRaises(TypeError):
            sgx_report_body.parse_from_bytes(1)
        with self.assertRaises(TypeError):
            sgx_report_body.parse_from_bytes(1.0)
        with self.assertRaises(TypeError):
            sgx_report_body.parse_from_bytes('')

        # Test an empty string, a string that is one too short, and a string
        # that is one too long
        with self.assertRaises(ValueError):
            sgx_report_body.parse_from_bytes(b'')
        with self.assertRaises(ValueError):
            sgx_report_body.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxReportBody.STRUCT_SIZE - 1))
        with self.assertRaises(ValueError):
            sgx_report_body.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxReportBody.STRUCT_SIZE + 1))

        # Simply verify that buffer of correct size unpacks without error
        sgx_report_body.parse_from_bytes(
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxReportBody.STRUCT_SIZE))

        # The report body is laid out as follows:
        #
        # sgx_cpu_svn_t           cpu_svn;        /* 0   */
        # sgx_misc_select_t       misc_select;    /* 16  */
        # uint8_t                 reserved1[28];  /* 20  */
        # sgx_attributes_t        attributes;     /* 48  */
        # sgx_measurement_t       mr_enclave;     /* 64  */
        # uint8_t                 reserved2[32];  /* 96  */
        # sgx_measurement_t       mr_signer;      /* 128 */
        # uint8_t                 reserved3[96];  /* 160 */
        # sgx_prod_id_t           isv_prod_id;    /* 256 */
        # sgx_isv_svn_t           isv_svn;        /* 258 */
        # uint8_t                 reserved4[60];  /* 260 */
        # sgx_report_data_t       report_data;    /* 320 */

        # sgx_cpu_svn = sgx_structs.SgxCpuSvn(cpu_svn=svn)
        # sgx_attributes = sgx_structs.SgxAttributes(flags=flags, xfrm=xfrm)
        # sgx_measurement_mr_enclave = sgx_structs.SgxMeasurement(m=mr_enclave)
        # sgx_measurement_mr_signer = sgx_structs.SgxMeasurement(m=mr_signer)
        # sgx_report_data = sgx_structs.SgxReportData(d=report_data)

        # Verify sgx_report_body unpacks properly
        svn = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxCpuSvn.STRUCT_SIZE)
        misc_select = 0x00010203
        reserved1 = b'\x00' * 28
        flags = 0x0405060708090a0b
        xfrm = 0x0c0d0e0f10111213
        mr_enclave = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxMeasurement.STRUCT_SIZE)
        reserved2 = b'\x00' * 32
        mr_signer = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxMeasurement.STRUCT_SIZE)
        reserved3 = b'\x00' * 96
        isv_prod_id = 0x1415
        isv_svn = 0x1617
        reserved4 = b'\x00' * 60
        report_data = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxReportData.STRUCT_SIZE)
        report_body = \
            struct.pack(
                '<{}sL{}sQQ{}s{}s{}s{}sHH{}s{}s'.format(
                    len(svn),
                    len(reserved1),
                    len(mr_enclave),
                    len(reserved2),
                    len(mr_signer),
                    len(reserved3),
                    len(reserved4),
                    len(report_data)
                ),
                svn,
                misc_select,
                reserved1,
                flags,
                xfrm,
                mr_enclave,
                reserved2,
                mr_signer,
                reserved3,
                isv_prod_id,
                isv_svn,
                reserved4,
                report_data)

        sgx_report_body.parse_from_bytes(report_body)

        self.assertTrue(sgx_report_body.cpu_svn.svn == svn)
        self.assertTrue(sgx_report_body.misc_select == misc_select)
        self.assertTrue(sgx_report_body.attributes.flags == flags)
        self.assertTrue(sgx_report_body.attributes.xfrm == xfrm)
        self.assertTrue(sgx_report_body.mr_enclave.m == mr_enclave)
        self.assertTrue(sgx_report_body.mr_signer.m == mr_signer)
        self.assertTrue(sgx_report_body.isv_prod_id == isv_prod_id)
        self.assertTrue(sgx_report_body.isv_svn == isv_svn)
        self.assertTrue(sgx_report_body.report_data.d == report_data)

        # Reset the object using the field values and verify that we
        # get expected serialized buffer
        sgx_cpu_svn = sgx_structs.SgxCpuSvn(svn=svn)
        sgx_attributes = sgx_structs.SgxAttributes(flags=flags, xfrm=xfrm)
        sgx_measurement_mr_enclave = sgx_structs.SgxMeasurement(m=mr_enclave)
        sgx_measurement_mr_signer = sgx_structs.SgxMeasurement(m=mr_signer)
        sgx_report_data = sgx_structs.SgxReportData(d=report_data)
        sgx_report_body = \
            sgx_structs.SgxReportBody(
                cpu_svn=sgx_cpu_svn,
                misc_select=misc_select,
                attributes=sgx_attributes,
                mr_enclave=sgx_measurement_mr_enclave,
                mr_signer=sgx_measurement_mr_signer,
                isv_prod_id=isv_prod_id,
                isv_svn=isv_svn,
                report_data=sgx_report_data)
        self.assertEqual(report_body, sgx_report_body.serialize_to_bytes())

    def test_sgx_key_id(self):
        sgx_key_id = sgx_structs.SgxKeyId()

        # Test with None and invalid types
        with self.assertRaises(TypeError):
            sgx_key_id.parse_from_bytes(None)
        with self.assertRaises(TypeError):
            sgx_key_id.parse_from_bytes([])
        with self.assertRaises(TypeError):
            sgx_key_id.parse_from_bytes({})
        with self.assertRaises(TypeError):
            sgx_key_id.parse_from_bytes(1)
        with self.assertRaises(TypeError):
            sgx_key_id.parse_from_bytes(1.0)
        with self.assertRaises(TypeError):
            sgx_key_id.parse_from_bytes('')

        # Test an empty string, a string that is one too short, and a string
        # that is one too long
        with self.assertRaises(ValueError):
            sgx_key_id.parse_from_bytes(b'')
        with self.assertRaises(ValueError):
            sgx_key_id.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxKeyId.STRUCT_SIZE - 1))
        with self.assertRaises(ValueError):
            sgx_key_id.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxKeyId.STRUCT_SIZE + 1))

        # Verify sgx_key_id unpacks properly
        key_id = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxKeyId.STRUCT_SIZE)
        sgx_key_id.parse_from_bytes(key_id)

        self.assertTrue(sgx_key_id.id == key_id)

        # Reset the object using the field values and verify that we
        # get expected serialized buffer
        sgx_key_id = sgx_structs.SgxKeyId(identifier=key_id)
        self.assertEqual(key_id, sgx_key_id.serialize_to_bytes())

    def test_sgx_report(self):
        sgx_report = sgx_structs.SgxReport()

        # Test with None and invalid types
        with self.assertRaises(TypeError):
            sgx_report.parse_from_bytes(None)
        with self.assertRaises(TypeError):
            sgx_report.parse_from_bytes([])
        with self.assertRaises(TypeError):
            sgx_report.parse_from_bytes({})
        with self.assertRaises(TypeError):
            sgx_report.parse_from_bytes(1)
        with self.assertRaises(TypeError):
            sgx_report.parse_from_bytes(1.0)
        with self.assertRaises(TypeError):
            sgx_report.parse_from_bytes('')

        # Test an empty string, a string that is one too short, and a string
        # that is one too long
        with self.assertRaises(ValueError):
            sgx_report.parse_from_bytes(b'')
        with self.assertRaises(ValueError):
            sgx_report.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxReport.STRUCT_SIZE - 1))
        with self.assertRaises(ValueError):
            sgx_report.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxReport.STRUCT_SIZE + 1))

        # Simply verify that buffer of correct size unpacks without error
        sgx_report.parse_from_bytes(
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxReport.STRUCT_SIZE))

        # The report body is laid out as follows:
        #
        # sgx_report_body_t   body;   /* 0   */
        # sgx_key_id_t        key_id; /* 384 */
        # sgx_mac_t           mac;    /* 416 */

        # Verify sgx_report unpacks properly
        svn = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxCpuSvn.STRUCT_SIZE)
        misc_select = 0x00010203
        reserved1 = b'\x00' * 28
        flags = 0x0405060708090a0b
        xfrm = 0x0c0d0e0f10111213
        mr_enclave = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxMeasurement.STRUCT_SIZE)
        reserved2 = b'\x00' * 32
        mr_signer = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxMeasurement.STRUCT_SIZE)
        reserved3 = b'\x00' * 96
        isv_prod_id = 0x1415
        isv_svn = 0x1617
        reserved4 = b'\x00' * 60
        report_data = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxReportData.STRUCT_SIZE)
        report_body = \
            struct.pack(
                '<{}sL{}sQQ{}s{}s{}s{}sHH{}s{}s'.format(
                    len(svn),
                    len(reserved1),
                    len(mr_enclave),
                    len(reserved2),
                    len(mr_signer),
                    len(reserved3),
                    len(reserved4),
                    len(report_data)
                ),
                svn,
                misc_select,
                reserved1,
                flags,
                xfrm,
                mr_enclave,
                reserved2,
                mr_signer,
                reserved3,
                isv_prod_id,
                isv_svn,
                reserved4,
                report_data)
        key_id = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxKeyId.STRUCT_SIZE)
        mac = TestSgxStructs.create_random_buffer(16)
        report = \
            struct.pack(
                '<{}s{}s{}s'.format(
                    len(report_body),
                    len(key_id),
                    len(mac)),
                report_body,
                key_id,
                mac)

        sgx_report.parse_from_bytes(report)

        self.assertTrue(sgx_report.body.cpu_svn.svn == svn)
        self.assertTrue(sgx_report.body.misc_select == misc_select)
        self.assertTrue(sgx_report.body.attributes.flags == flags)
        self.assertTrue(sgx_report.body.attributes.xfrm == xfrm)
        self.assertTrue(sgx_report.body.mr_enclave.m == mr_enclave)
        self.assertTrue(sgx_report.body.mr_signer.m == mr_signer)
        self.assertTrue(sgx_report.body.isv_prod_id == isv_prod_id)
        self.assertTrue(sgx_report.body.isv_svn == isv_svn)
        self.assertTrue(sgx_report.body.report_data.d == report_data)
        self.assertTrue(sgx_report.key_id.id == key_id)
        self.assertTrue(sgx_report.mac == mac)

        # Reset the object using the field values and verify that we
        # get expected serialized buffer
        sgx_cpu_svn = sgx_structs.SgxCpuSvn(svn=svn)
        sgx_attributes = sgx_structs.SgxAttributes(flags=flags, xfrm=xfrm)
        sgx_measurement_mr_enclave = sgx_structs.SgxMeasurement(m=mr_enclave)
        sgx_measurement_mr_signer = sgx_structs.SgxMeasurement(m=mr_signer)
        sgx_report_data = sgx_structs.SgxReportData(d=report_data)
        sgx_report_body = \
            sgx_structs.SgxReportBody(
                cpu_svn=sgx_cpu_svn,
                misc_select=misc_select,
                attributes=sgx_attributes,
                mr_enclave=sgx_measurement_mr_enclave,
                mr_signer=sgx_measurement_mr_signer,
                isv_prod_id=isv_prod_id,
                isv_svn=isv_svn,
                report_data=sgx_report_data)
        sgx_key_id = sgx_structs.SgxKeyId(identifier=key_id)
        sgx_report = \
            sgx_structs.SgxReport(
                body=sgx_report_body,
                key_id=sgx_key_id,
                mac=mac)
        self.assertEqual(report, sgx_report.serialize_to_bytes())

    def test_sgx_basename(self):
        sgx_basename = sgx_structs.SgxBasename()

        # Test with None and invalid types
        with self.assertRaises(TypeError):
            sgx_basename.parse_from_bytes(None)
        with self.assertRaises(TypeError):
            sgx_basename.parse_from_bytes([])
        with self.assertRaises(TypeError):
            sgx_basename.parse_from_bytes({})
        with self.assertRaises(TypeError):
            sgx_basename.parse_from_bytes(1)
        with self.assertRaises(TypeError):
            sgx_basename.parse_from_bytes(1.0)
        with self.assertRaises(TypeError):
            sgx_basename.parse_from_bytes('')

        # Test an empty string, a string that is one too short, and a string
        # that is one too long
        with self.assertRaises(ValueError):
            sgx_basename.parse_from_bytes(b'')
        with self.assertRaises(ValueError):
            sgx_basename.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxBasename.STRUCT_SIZE - 1))
        with self.assertRaises(ValueError):
            sgx_basename.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxBasename.STRUCT_SIZE + 1))

        # Verify sgx_basename unpacks properly
        basename = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxBasename.STRUCT_SIZE)
        sgx_basename.parse_from_bytes(basename)

        self.assertTrue(sgx_basename.name == basename)

        # Reset the object using the field values and verify that we
        # get expected serialized buffer
        sgx_basename = sgx_structs.SgxBasename(name=basename)
        self.assertEqual(basename, sgx_basename.serialize_to_bytes())

    def test_sgx_quote(self):
        sgx_quote = sgx_structs.SgxQuote()

        # Test with None and invalid types
        with self.assertRaises(TypeError):
            sgx_quote.parse_from_bytes(None)
        with self.assertRaises(TypeError):
            sgx_quote.parse_from_bytes([])
        with self.assertRaises(TypeError):
            sgx_quote.parse_from_bytes({})
        with self.assertRaises(TypeError):
            sgx_quote.parse_from_bytes(1)
        with self.assertRaises(TypeError):
            sgx_quote.parse_from_bytes(1.0)
        with self.assertRaises(TypeError):
            sgx_quote.parse_from_bytes('')

        # Test an empty string and a buffer one too small
        with self.assertRaises(ValueError):
            sgx_quote.parse_from_bytes(b'')
        with self.assertRaises(ValueError):
            sgx_quote.parse_from_bytes(
                b'\x00' * (sgx_structs.SgxQuote.FIXED_STRUCT_SIZE - 1))

        # typedef uint8_t sgx_epid_group_id_t[4];
        # typedef uint16_t sgx_isv_svn_t;

        # uint16_t            version;                /* 0   */
        # uint16_t            sign_type;              /* 2   */
        # sgx_epid_group_id_t epid_group_id;          /* 4   */
        # sgx_isv_svn_t       qe_svn;                 /* 8   */
        # sgx_isv_svn_t       pce_svn;                /* 10  */
        # uint32_t            extended_epid_group_id; /* 12  */
        # sgx_basename_t      basename;               /* 16  */
        # sgx_report_body_t   report_body;            /* 48  */
        # uint32_t            signature_len;          /* 432 */
        # uint8_t             signature[];            /* 436 */

        # Verify sgx_quote unpacks properly
        version = 0x0102
        sign_type = 0x0304
        epid_group_id = TestSgxStructs.create_random_buffer(4)
        qe_svn = 0x0506
        pce_svn = 0x0708
        extended_epid_group_id = 0x090a0b0c
        basename = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxBasename.STRUCT_SIZE)
        svn = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxCpuSvn.STRUCT_SIZE)
        misc_select = 0x0d0e0f10
        reserved1 = b'\x00' * 28
        flags = 0x1112131415161718
        xfrm = 0x191a1b1c1d1e1f20
        mr_enclave = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxMeasurement.STRUCT_SIZE)
        reserved2 = b'\x00' * 32
        mr_signer = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxMeasurement.STRUCT_SIZE)
        reserved3 = b'\x00' * 96
        isv_prod_id = 0x2122
        isv_svn = 0x2324
        reserved4 = b'\x00' * 60
        report_data = \
            TestSgxStructs.create_random_buffer(
                sgx_structs.SgxReportData.STRUCT_SIZE)
        report_body = \
            struct.pack(
                '<{}sL{}sQQ{}s{}s{}s{}sHH{}s{}s'.format(
                    len(svn),
                    len(reserved1),
                    len(mr_enclave),
                    len(reserved2),
                    len(mr_signer),
                    len(reserved3),
                    len(reserved4),
                    len(report_data)
                ),
                svn,
                misc_select,
                reserved1,
                flags,
                xfrm,
                mr_enclave,
                reserved2,
                mr_signer,
                reserved3,
                isv_prod_id,
                isv_svn,
                reserved4,
                report_data)
        quote = \
            struct.pack(
                '<HH{}sHHL{}s{}s'.format(
                    len(epid_group_id),
                    len(basename),
                    len(report_body)),
                version,
                sign_type,
                epid_group_id,
                qe_svn,
                pce_svn,
                extended_epid_group_id,
                basename,
                report_body)

        sgx_quote.parse_from_bytes(quote)

        self.assertTrue(sgx_quote.version == version)
        self.assertTrue(sgx_quote.sign_type == sign_type)
        self.assertTrue(sgx_quote.epid_group_id == epid_group_id)
        self.assertTrue(sgx_quote.qe_svn == qe_svn)
        self.assertTrue(sgx_quote.pce_svn == pce_svn)
        self.assertTrue(sgx_quote.basename.name == basename)
        self.assertTrue(sgx_quote.report_body.cpu_svn.svn == svn)
        self.assertTrue(sgx_quote.report_body.misc_select == misc_select)
        self.assertTrue(sgx_quote.report_body.attributes.flags == flags)
        self.assertTrue(sgx_quote.report_body.attributes.xfrm == xfrm)
        self.assertTrue(sgx_quote.report_body.mr_enclave.m == mr_enclave)
        self.assertTrue(sgx_quote.report_body.mr_signer.m == mr_signer)
        self.assertTrue(sgx_quote.report_body.isv_prod_id == isv_prod_id)
        self.assertTrue(sgx_quote.report_body.isv_svn == isv_svn)
        self.assertTrue(sgx_quote.report_body.report_data.d == report_data)

        # Add a few bytes so that the signature length is partial.  Should
        # fail.
        bad_quote = quote[:]
        for _ in range(3):
            bad_quote += TestSgxStructs.create_random_buffer(1)
            with self.assertRaises(ValueError):
                sgx_quote.parse_from_bytes(bad_quote)

        # Add a non-zero signature length, but don't add a signature.  Should
        # fail.
        bad_quote = struct.pack('<{}sL'.format(len(quote)), quote, 4)
        with self.assertRaises(ValueError):
            sgx_quote.parse_from_bytes(bad_quote)

        # Add a signature that is too short
        short_signature = TestSgxStructs.create_random_buffer(31)
        bad_quote = \
            struct.pack(
                '<{}sL{}s'.format(
                    len(quote),
                    len(short_signature)),
                quote,
                len(short_signature) + 1,
                short_signature)
        with self.assertRaises(ValueError):
            sgx_quote.parse_from_bytes(bad_quote)

        # Add a signature length of zero without a signature and verify
        unsigned_quote = struct.pack('<{}sL'.format(len(quote)), quote, 0)

        sgx_quote.parse_from_bytes(unsigned_quote)

        self.assertTrue(sgx_quote.version == version)
        self.assertTrue(sgx_quote.sign_type == sign_type)
        self.assertTrue(sgx_quote.epid_group_id == epid_group_id)
        self.assertTrue(sgx_quote.qe_svn == qe_svn)
        self.assertTrue(sgx_quote.pce_svn == pce_svn)
        self.assertTrue(sgx_quote.basename.name == basename)
        self.assertTrue(sgx_quote.report_body.cpu_svn.svn == svn)
        self.assertTrue(sgx_quote.report_body.misc_select == misc_select)
        self.assertTrue(sgx_quote.report_body.attributes.flags == flags)
        self.assertTrue(sgx_quote.report_body.attributes.xfrm == xfrm)
        self.assertTrue(sgx_quote.report_body.mr_enclave.m == mr_enclave)
        self.assertTrue(sgx_quote.report_body.mr_signer.m == mr_signer)
        self.assertTrue(sgx_quote.report_body.isv_prod_id == isv_prod_id)
        self.assertTrue(sgx_quote.report_body.isv_svn == isv_svn)
        self.assertTrue(sgx_quote.report_body.report_data.d == report_data)
        self.assertTrue(sgx_quote.signature_len == 0)

        # Add a good signature and verify
        signature = TestSgxStructs.create_random_buffer(32)
        signed_quote = \
            struct.pack(
                '<{}sL{}s'.format(
                    len(quote),
                    len(signature)),
                quote,
                len(signature),
                signature)

        sgx_quote.parse_from_bytes(signed_quote)

        self.assertTrue(sgx_quote.version == version)
        self.assertTrue(sgx_quote.sign_type == sign_type)
        self.assertTrue(sgx_quote.epid_group_id == epid_group_id)
        self.assertTrue(sgx_quote.qe_svn == qe_svn)
        self.assertTrue(sgx_quote.pce_svn == pce_svn)
        self.assertTrue(sgx_quote.basename.name == basename)
        self.assertTrue(sgx_quote.report_body.cpu_svn.svn == svn)
        self.assertTrue(sgx_quote.report_body.misc_select == misc_select)
        self.assertTrue(sgx_quote.report_body.attributes.flags == flags)
        self.assertTrue(sgx_quote.report_body.attributes.xfrm == xfrm)
        self.assertTrue(sgx_quote.report_body.mr_enclave.m == mr_enclave)
        self.assertTrue(sgx_quote.report_body.mr_signer.m == mr_signer)
        self.assertTrue(sgx_quote.report_body.isv_prod_id == isv_prod_id)
        self.assertTrue(sgx_quote.report_body.isv_svn == isv_svn)
        self.assertTrue(sgx_quote.report_body.report_data.d == report_data)
        self.assertTrue(sgx_quote.signature_len == len(signature))
        self.assertTrue(sgx_quote.signature == signature)

        # Reset the object using the field values and verify that we
        # get expected serialized buffer
        sgx_basename = sgx_structs.SgxBasename(name=basename)
        sgx_cpu_svn = sgx_structs.SgxCpuSvn(svn=svn)
        sgx_attributes = sgx_structs.SgxAttributes(flags=flags, xfrm=xfrm)
        sgx_measurement_mr_enclave = sgx_structs.SgxMeasurement(m=mr_enclave)
        sgx_measurement_mr_signer = sgx_structs.SgxMeasurement(m=mr_signer)
        sgx_report_data = sgx_structs.SgxReportData(d=report_data)
        sgx_report_body = \
            sgx_structs.SgxReportBody(
                cpu_svn=sgx_cpu_svn,
                misc_select=misc_select,
                attributes=sgx_attributes,
                mr_enclave=sgx_measurement_mr_enclave,
                mr_signer=sgx_measurement_mr_signer,
                isv_prod_id=isv_prod_id,
                isv_svn=isv_svn,
                report_data=sgx_report_data)
        sgx_quote = sgx_structs.SgxQuote(
            version=version,
            sign_type=sign_type,
            epid_group_id=epid_group_id,
            qe_svn=qe_svn,
            pce_svn=pce_svn,
            extended_epid_group_id=extended_epid_group_id,
            basename=sgx_basename,
            report_body=sgx_report_body)

        self.assertEqual(quote, sgx_quote.serialize_to_bytes()[:len(quote)])

        # Verify that zero signature serializes successfully
        zero_sign_quote = struct.pack('<{}sL'.format(len(quote)), quote, 0)

        self.assertEqual(zero_sign_quote, sgx_quote.serialize_to_bytes())

        # Verify that non-zero signature serializes successfully
        non_zero_sign_quote = \
            struct.pack(
                '<{}sL{}s'.format(
                    len(quote),
                    len(signature)),
                quote,
                len(signature),
                signature)
        sgx_quote.signature_len = len(signature)
        sgx_quote.signature = signature
        self.assertEqual(non_zero_sign_quote, sgx_quote.serialize_to_bytes())


if __name__ == '__main__':
    unittest.main()

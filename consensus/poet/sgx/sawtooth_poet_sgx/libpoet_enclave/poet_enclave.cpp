/*
 Copyright 2017 Intel Corporation

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
------------------------------------------------------------------------------
*/

#include "poet_enclave_t.h"

#include <limits.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <float.h>

#include <algorithm>
#include <map>
#include <vector>
#include <iterator>
#include <cctype>

#include <sgx_tae_service.h> //sgx_time_t, sgx_time_source_nonce_t, sgx_get_trusted_time
#include <sgx_trts.h>
#include <sgx_tcrypto.h>
#include <sgx_tkey_exchange.h>
#include <sgx_utils.h> // sgx_get_key, sgx_create_report
#include <sgx_key.h>

#include "parson.h"

#include "poet.h"
#include "error.h"
#include "zero.h"
#include "hex_string.h"
#include "public_key_util.h"

#include "utils_enclave.h"
#include "auto_handle_sgx.h"

namespace sp = sawtooth::poet;

typedef struct {
    sgx_ec256_private_t privateKey;
    sgx_ec256_public_t publicKey;
    sgx_mc_uuid_t counterId;
} ValidatorSignupData;

static const std::string    NULL_IDENTIFIER = "0000000000000000";
static const uint32_t       WAIT_CERTIFICATE_NONCE_LENGTH = 32;

// Timers, once expired, should not be usuable indefinitely.
// This constant allows a 30-second window after expiration for
// which a timer may be used to create a wait certificate.
static const double         TIMER_TIMEOUT_PERIOD = 30.0;
// Minimum wait time duration
static const double         MINIMUM_WAIT_TIME = 1.0;

#if defined(SGX_SIMULATOR)
    static const bool IS_SGX_SIMULATOR = true;
#else
    static const bool IS_SGX_SIMULATOR = false;
#endif

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
/*
ECDSA public key generated. Note the 8 magic bytes are removed and
x and y component are changed to little endian . The public key is hard coded in the enclave
*/
//  DRD generated public key
static const sgx_ec256_public_t g_sp_pub_key = {
    {
        0xC0, 0x8C, 0x9F, 0x45, 0x59, 0x1A, 0x9F, 0xAE, 0xC5, 0x1F, 0xBC, 0x3E, 0xFB, 0x4F, 0x67, 0xB1,
        0x93, 0x61, 0x45, 0x9E, 0x30, 0x27, 0x10, 0xC4, 0x92, 0x0F, 0xBB, 0xB2, 0x69, 0xB0, 0x16, 0x39
    },
    {
        0x5D, 0x98, 0x6B, 0x24, 0x2B, 0x52, 0x46, 0x72, 0x2A, 0x35, 0xCA, 0xE0, 0xA9, 0x1A, 0x6A, 0xDC,
        0xB8, 0xEB, 0x32, 0xC8, 0x1C, 0x2B, 0x5A, 0xF1, 0x23, 0x1F, 0x6C, 0x6E, 0x30, 0x00, 0x96, 0x4F
    }
};


// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
// XX Declaration of static helper functions                         XX
// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

static void printf(
    const char* fmt,
    ...
    );

static void Log(
    int         level,
    const char* fmt,
    ...);

static void CreateSignupReportData(
    const char*                 pOriginatorPublicKeyHash,
    const sgx_ec256_public_t*   pPoetPublicKey,
    sgx_report_data_t*          pReportData
    );

static double GenerateWaitTimerDuration(
    const std::string&          validatorAddress,
    const std::string&          previousCertificateId,
    double                      localMean
    );

static sgx_time_t GetCurrentTime(
    sgx_time_source_nonce_t*    pNonce = nullptr
    );

static void ParseWaitTimer(
    const char*                 pSerializedWaitTimer,
    WaitTimer&                  waitTimer
    );

static size_t CalculateSealedSignupDataSize();

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
// XX External interface                                             XX
// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
/*
This ecall is a wrapper of sgx_ra_init to create the trusted
KE exchange key context needed for the remote attestation
SIGMA API's. Input pointers aren't checked since the trusted stubs
copy them into EPC memory.

@param p_context Pointer to the location where the returned key
    context is to be copied.
@return Any error returned during the initialization process.
*/
poet_err_t ecall_Initialize(sgx_ra_context_t *p_context)
{
    poet_err_t result = POET_SUCCESS;

    try {
        // Test that we can access platform services
        PseSession session;

        /* sgx initialization function where the ECDSA generated
        public key is passed as one of the parameters
        returns the context to the application
        */
        sgx_status_t ret = sgx_ra_init(&g_sp_pub_key, true, p_context);
        sp::ThrowSgxError(ret, "Failed to initialize Remote Attestation.");
    } catch (sp::PoetError& e) {
        Log(
            POET_LOG_ERROR,
            "Error in poet enclave(ecall_Initialize): %04X -- %s",
            e.error_code(),
            e.what());
        ocall_SetErrorMessage(e.what());
        result = e.error_code();
    } catch (...) {
        Log(POET_LOG_ERROR, "Unknown error in poet enclave(ecall_Initialize)");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // ecall_Initialize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t ecall_CreateErsatzEnclaveReport(
    sgx_target_info_t* targetInfo,
    sgx_report_t* outReport
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        sp::ThrowIfNull(targetInfo, "targetInfo is not valid");
        sp::ThrowIfNull(outReport, "outReport is not valid");

        Zero(outReport, sizeof(*outReport));

        // Create a relatively useless enclave report.  Well....the report
        // itself is not useful for anything except that it can be used to
        // create SGX quotes, which contain potentially useful information
        // (like the enclave basename, mr_enclave, etc.).
        sp::ThrowSgxError(
            sgx_create_report(targetInfo, nullptr, outReport),
            "Failed to create report.");
    } catch (sp::PoetError& e) {
        Log(
            POET_LOG_ERROR,
            "Error in poet enclave(ecall_CreateErsatzEnclaveReport): %04X "
            "-- %s",
            e.error_code(),
            e.what());
        ocall_SetErrorMessage(e.what());
        result = e.error_code();
    } catch (...) {
        Log(
            POET_LOG_ERROR,
            "Unknown error in poet enclave(ecall_CreateErsatzEnclaveReport)");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // ecall_CreateErsatzEnclaveReport

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t ecall_GetPseManifestHash(
    sgx_sha256_hash_t* outPseManifestHash
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        sp::ThrowIfNull(
            outPseManifestHash,
            "PSE manifest hash pointer is NULL");

        // Grab the PSE manifest and the compute the SHA256 hash of it.
        // We need a PSE session first.  The session will automatically clean
        // up after itself.
        PseSession session;
        sgx_ps_sec_prop_desc_t pseManifest;
        sp::ThrowSgxError(
            sgx_get_ps_sec_prop(
                &pseManifest),
                "Failed to create PSE manifest");
        sp::ThrowSgxError(
            sgx_sha256_msg(
                reinterpret_cast<const uint8_t *>(&pseManifest),
                sizeof(pseManifest),
                outPseManifestHash),
                "Failed to hash PSE manifest");
    } catch (sp::PoetError& e) {
        Log(
            POET_LOG_ERROR,
            "Error in poet enclave(ecall_GetPseManifest): %04X -- %s",
            e.error_code(),
            e.what());
        ocall_SetErrorMessage(e.what());
        result = e.error_code();
    } catch (...) {
        Log(
            POET_LOG_ERROR,
            "Unknown error in poet enclave(ecall_GetPseManifest)");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // ecall_GetPseManifestHash

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t ecall_CalculateSealedSignupDataSize(
    size_t* pSealedSignupDataSize
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        sp::ThrowIfNull(
            pSealedSignupDataSize,
            "Sealed signup data size pointer is NULL");

        *pSealedSignupDataSize = CalculateSealedSignupDataSize();
    } catch (sp::PoetError& e) {
        Log(
            POET_LOG_ERROR,
            "Error in poet enclave(ecall_CalculateSealedSignupDataSize): "
            "%04X -- %s",
            e.error_code(),
            e.what());
        ocall_SetErrorMessage(e.what());
        result = e.error_code();
    } catch (...) {
        Log(
            POET_LOG_ERROR,
            "Unknown error in poet enclave(ecall_"
            "CalculateSealedSignupDataSize)");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // ecall_CalculateSealedSignupDataSize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t ecall_CreateSignupData(
    const sgx_target_info_t* inTargetInfo,
    const char* inOriginatorPublicKeyHash,
    sgx_ec256_public_t* outPoetPublicKey,
    sgx_report_t* outEnclaveReport,
    uint8_t* outSealedSignupData,
    size_t inSealedSignupDataSize,
    sgx_ps_sec_prop_desc_t* outPseManifest
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        sp::ThrowIfNull(inTargetInfo, "Target info pointer is NULL");
        sp::ThrowIfNull(
            inOriginatorPublicKeyHash,
            "Originator public key hash pointer is NULL");
        sp::ThrowIfNull(outPoetPublicKey, "PoET public key pointer is NULL");
        sp::ThrowIfNull(outEnclaveReport, "SGX report pointer is NULL");
        sp::ThrowIfNull(
            outSealedSignupData,
            "Sealed signup data pointer is NULL");
        sp::ThrowIf<sp::ValueError>(
            inSealedSignupDataSize != CalculateSealedSignupDataSize(),
            "Sealed signup data buffer is not the correct size");
        sp::ThrowIfNull(outPseManifest, "PSE manifest pointer is NULL");

        PseSession session;

        // First we need to generate a PoET public/private key pair.  The ECC
        // state handle cleans itself up automatically.
        Intel::SgxEcc256StateHandle eccStateHandle;
        ValidatorSignupData validatorSignupData;

        sgx_status_t ret = sgx_ecc256_open_context(&eccStateHandle);
        sp::ThrowSgxError(ret, "Failed to create ECC256 context");

        ret =
            sgx_ecc256_create_key_pair(
                &validatorSignupData.privateKey,
                &validatorSignupData.publicKey,
                eccStateHandle);
        sp::ThrowSgxError(
            ret,
            "Failed to create PoET public/private key pair");

        // Create the monotonic counter bound to the keypair
        uint32_t initialCounterValue = 0;
        ret =
            sgx_create_monotonic_counter(
                &validatorSignupData.counterId,
                &initialCounterValue);
        sp::ThrowSgxError(ret, "Failed to create monotonic counter.");

        // Create the report data we want embedded in the enclave report.
        sgx_report_data_t reportData = { 0 };
        CreateSignupReportData(
            inOriginatorPublicKeyHash,
            &validatorSignupData.publicKey,
            &reportData);

        ret = sgx_create_report(inTargetInfo, &reportData, outEnclaveReport);
        sp::ThrowSgxError(ret, "Failed to create enclave report");

        // Now get the PSE manifest into the caller's buffer.
        sp::ThrowSgxError(
            sgx_get_ps_sec_prop(outPseManifest),
            "Failed to create PSE manifest");

        // Seal up the signup data into the caller's buffer.
        // NOTE - the attributes mask 0xfffffffffffffff3 seems rather
        // arbitrary, but according to SGX SDK documentation, this is
        // what sgx_seal_data uses, so it is good enough for us.
        sgx_attributes_t attributes = { 0xfffffffffffffff3, 0 };
        ret =
            sgx_seal_data_ex(
                SGX_KEYPOLICY_MRENCLAVE,
                attributes,
                0,
                0,
                nullptr,
                sizeof(validatorSignupData),
                reinterpret_cast<const uint8_t *>(&validatorSignupData),
                static_cast<uint32_t>(inSealedSignupDataSize),
                reinterpret_cast<sgx_sealed_data_t *>(outSealedSignupData));
        sp::ThrowSgxError(ret, "Failed to seal signup data");

        // Give the caller a copy of the PoET public key
        memcpy(
            outPoetPublicKey,
            &validatorSignupData.publicKey,
            sizeof(*outPoetPublicKey));
    } catch (sp::PoetError& e) {
        Log(
            POET_LOG_ERROR,
            "Error in poet enclave(ecall_CreateSignupData): %04X -- %s",
            e.error_code(),
            e.what());
        ocall_SetErrorMessage(e.what());
        result = e.error_code();
    } catch (...) {
        Log(
            POET_LOG_ERROR,
            "Unknown error in poet enclave(ecall_CreateSignupData)");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // ecall_CreateSignupData

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t ecall_UnsealSignupData(
    const uint8_t* inSealedSignupData,
    size_t inSealedSignupDataSize,
    sgx_ec256_public_t* outPoetPublicKey
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        sp::ThrowIfNull(outPoetPublicKey, "PoET public key pointer is NULL");

        // Unseal the data
        ValidatorSignupData validatorSignupData;
        uint32_t decryptedLength = sizeof(validatorSignupData);
        sgx_status_t ret =
            sgx_unseal_data(
                reinterpret_cast<const sgx_sealed_data_t *>(
                    inSealedSignupData),
                nullptr,
                0,
                reinterpret_cast<uint8_t *>(&validatorSignupData),
                &decryptedLength);
        sp::ThrowSgxError(ret, "Failed to unseal signup data");

        sp::ThrowIf<sp::ValueError>(
            decryptedLength != sizeof(validatorSignupData),
            "Sealed signup data didn't decrypt to expected length");

        // Maker sure the counter is still valid
        uint32_t v = 0;
        PseSession session;
        ret = sgx_read_monotonic_counter(&validatorSignupData.counterId, &v);
        sp::ThrowSgxError(ret, "Failed to unseal counter");

        // Give the caller a copy of the PoET public key
        memcpy(
            outPoetPublicKey,
            &validatorSignupData.publicKey,
            sizeof(*outPoetPublicKey));
    } catch (sp::PoetError& e) {
        Log(
            POET_LOG_ERROR,
            "Error in poet enclave(ecall_UnsealSignupData): %04X -- %s",
            e.error_code(),
            e.what());
        ocall_SetErrorMessage(e.what());
        result = e.error_code();
    } catch (...) {
        Log(
            POET_LOG_ERROR,
            "Unknown error in poet enclave(ecall_UnsealSignupData)");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // ecall_UnsealSignupData

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t ecall_ReleaseSignupData(
    const uint8_t* inSealedSignupData,
    size_t inSealedSignupDataSize
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        // Unseal the data
        ValidatorSignupData validatorSignupData;
        uint32_t decryptedLength = sizeof(validatorSignupData);
        sgx_status_t ret =
            sgx_unseal_data(
                reinterpret_cast<const sgx_sealed_data_t *>(
                    inSealedSignupData),
                nullptr,
                0,
                reinterpret_cast<uint8_t *>(&validatorSignupData),
                &decryptedLength);
        sp::ThrowSgxError(ret, "Failed to unseal signup data");

        sp::ThrowIf<sp::ValueError>(
            decryptedLength != sizeof(validatorSignupData),
            "Sealed signup data didn't decrypt to expected length");

        PseSession session;
        ret = sgx_destroy_monotonic_counter(
            &validatorSignupData.counterId);
        sp::ThrowSgxError(ret, "Failed to destroy monotonic counter.");
    } catch (sp::PoetError& e) {
        Log(
            POET_LOG_ERROR,
            "Error in poet enclave(ecall_ReleaseSignupData): %04X -- %s",
            e.error_code(),
            e.what());
        ocall_SetErrorMessage(e.what());
        result = e.error_code();
    } catch (...) {
        Log(
            POET_LOG_ERROR,
            "Unknown error in poet enclave(ecall_ReleaseSignupData)");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // ecall_ReleaseSignupData

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t ecall_VerifySignupInfo(
    const sgx_target_info_t* inTargetInfo,
    const char* inOriginatorPublicKeyHash,
    const sgx_ec256_public_t* inPoetPublicKey,
    const sgx_sha256_hash_t* inPseManifestHash,
    sgx_report_t* outEnclaveReport
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        sp::ThrowIfNull(
            inTargetInfo,
            "Target info pointer is NULL");
        sp::ThrowIfNull(
            inOriginatorPublicKeyHash,
            "Originator public key hash pointer is NULL");
        sp::ThrowIfNull(
            inPoetPublicKey,
            "PoET public key pointer is NULL");
        sp::ThrowIfNull(inPseManifestHash, "PSE manifest hash pointer is NULL");
        sp::ThrowIfNull(
            outEnclaveReport,
            "Enclave report pointer is NULL");

        PseSession scopedPseSession;

        // Now get the PSE manifest, compute a hash of it, and compare it to
        // the hash provided..
        sgx_ps_sec_prop_desc_t  pseManifest;
        sgx_status_t ret = sgx_get_ps_sec_prop(&pseManifest);
            sp::ThrowSgxError(ret, "Failed to create PSE manifest");

        // Hash the PSE manifest and then compare
        sgx_sha256_hash_t pseManifestHash;
        ret =
            sgx_sha256_msg(
                reinterpret_cast<const uint8_t *>(&pseManifest),
                sizeof(pseManifest),
                &pseManifestHash);
        sp::ThrowSgxError(ret, "Failed to hash PSE manifest");

        sp::ThrowIf<sp::ValueError>(
            memcmp(
                inPseManifestHash,
                &pseManifestHash,
                sizeof(pseManifestHash)) != 0,
            "PSE manifest hash does not match expected value");

        // Create the report data we think should be given the OPK hash and the
        // PPK.
        sgx_report_data_t expectedReportData = { 0 };
        CreateSignupReportData(
            inOriginatorPublicKeyHash,
            inPoetPublicKey,
            &expectedReportData);

        // Create the enclave report for the caller.
        ret =
            sgx_create_report(
                inTargetInfo,
                &expectedReportData,
                outEnclaveReport);
        sp::ThrowSgxError(ret, "Failed to create enclave report");
    } catch (sp::PoetError& e) {
        Log(
            POET_LOG_ERROR,
            "Error in poet enclave(ecall_VerifySignupInfo): %04X -- %s",
            e.error_code(),
            e.what());
        ocall_SetErrorMessage(e.what());
        result = e.error_code();
    } catch (...) {
        Log(
            POET_LOG_ERROR,
            "Unknown error in poet enclave(ecall_VerifySignupInfo)");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // ecall_VerifySignupInfo

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t ecall_CreateWaitTimer(
    const uint8_t* inSealedSignupData,
    size_t inSealedSignupDataSize,
    const char* inValidatorAddress,
    const char* inPreviousCertificateId,
    double inRequestTime,
    double inLocalMean,
    char* outSerializedTimer,
    size_t inSerializedTimerLength,
    sgx_ec256_signature_t* outTimerSignature
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        sp::ThrowIfNull(
            inSealedSignupData,
            "Sealed Signup Data pointer is NULL");
        sp::ThrowIfNull(
            inValidatorAddress,
            "Validator address pointer is NULL");
        sp::ThrowIfNull(
            inPreviousCertificateId,
            "Previous certificate ID pointer is NULL");
        sp::ThrowIfNull(outSerializedTimer, "Serialized timer pointer is NULL");
        sp::ThrowIfNull(outTimerSignature, "Timer signature pointer is NULL");

        std::string validatorAddress(inValidatorAddress);
        std::string previousCertificateId(inPreviousCertificateId);

        PseSession session;
        // Unseal the data
        ValidatorSignupData validatorSignupData;
        uint32_t decryptedLength = sizeof(validatorSignupData);
        sgx_status_t ret =
            sgx_unseal_data(
                reinterpret_cast<const sgx_sealed_data_t *>(
                    inSealedSignupData),
                nullptr,
                0,
                reinterpret_cast<uint8_t *>(&validatorSignupData),
                &decryptedLength);
        sp::ThrowSgxError(ret, "Failed to unseal signup data");

        sp::ThrowIf<sp::ValueError>(
            decryptedLength != sizeof(validatorSignupData),
            "Sealed signup data didn't decrypt to expected length");

        // Get the current sgx time (as a time basis)
        sgx_time_source_nonce_t timeSourceNonce;
        double sgx_request_time =
            static_cast<double>(GetCurrentTime(&timeSourceNonce));
        double duration =
            GenerateWaitTimerDuration(
                validatorAddress,
                previousCertificateId,
                inLocalMean);

        // Get the sequence ID (prevent replay) for this timer
        uint32_t sequenceId = 0;
        ret = sgx_increment_monotonic_counter(
            &validatorSignupData.counterId,
            &sequenceId);
        sp::ThrowSgxError(ret, "Failed to increment monotonic counter.");

        // Create serialized WaitTimer
        JsonValue waitTimerValue(json_value_init_object());
        sp::ThrowIf<sp::RuntimeError>(
            !waitTimerValue.value,
            "WaitTimer serialization failed on creation of JSON object.");

        JSON_Object* waitTimerObject = json_value_get_object(waitTimerValue);
        JSON_Status jret;

        // Use alphabetical order for the keys to ensure predictable
        // serialization
        jret = json_object_dotset_number(
            waitTimerObject,
            "Duration",
            duration);
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitTimer serialization failed on Duration.");
        jret = json_object_dotset_number(
            waitTimerObject,
            "LocalMean",
            inLocalMean);
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitTimer serialization failed on LocalMean.");
        jret = json_object_dotset_string(
            waitTimerObject,
            "PreviousCertID",
            previousCertificateId.c_str());
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitTimer serialization failed on PreviousCertId.");
        jret = json_object_dotset_number(
            waitTimerObject,
            "RequestTime",
            inRequestTime);
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitTimer serialization failed on RequestTime.");
        jret = json_object_dotset_number(
            waitTimerObject,
            "SequenceId",
            sequenceId);
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitTimer serialization failed on SequenceId.");
        jret = json_object_dotset_number(
            waitTimerObject,
            "SgxRequestTime",
            sgx_request_time);
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitTimer serialization failed on SgxRequestTime.");
        jret = json_object_dotset_string(
            waitTimerObject,
            "ValidatorAddress",
            validatorAddress.c_str());
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitTimer serialization failed on ValidatorAddress.");

        size_t serializedSize = json_serialization_size(waitTimerValue);
        sp::ThrowIf<sp::ValueError>(
            inSerializedTimerLength < serializedSize,
            "WaitTimer buffer (outSerializedTimer) is too small");

        jret =
            json_serialize_to_buffer(
                waitTimerValue,
                outSerializedTimer,
                serializedSize);
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitTimer serialization failed.");

        // Sign the serialized timer using the PoET secret key. The handle
        // will close automatically for us.
        Intel::SgxEcc256StateHandle eccStateHandle;

        ret = sgx_ecc256_open_context(&eccStateHandle);
        sp::ThrowSgxError(ret, "Failed to create ECC256 context");

        ret =
            sgx_ecdsa_sign(
                reinterpret_cast<const uint8_t *>(outSerializedTimer),
                static_cast<int32_t>(strlen(outSerializedTimer)),
                const_cast<sgx_ec256_private_t *>(
                    &validatorSignupData.privateKey),
                outTimerSignature,
                eccStateHandle);
        sp::ThrowSgxError(ret, "Failed to sign wait timer");
    } catch (sp::PoetError& e) {
        Log(
            POET_LOG_ERROR,
            "Error in poet enclave(ecall_CreateWaitTimer): %04X -- %s",
            e.error_code(),
            e.what());
        ocall_SetErrorMessage(e.what());
        result = e.error_code();
    } catch (...) {
        Log(
            POET_LOG_ERROR,
            "Unknown error in poet enclave(ecall_CreateWaitTimer)");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // ecall_CreateWaitTimer

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t ecall_CreateWaitCertificate(
    const uint8_t* inSealedSignupData,
    size_t inSealedSignupDataSize,
    const char* inSerializedWaitTimer,
    const sgx_ec256_signature_t* inWaitTimerSignature,
    const char* inBlockHash,
    char* outSerializedWaitCertificate,
    size_t inSerializedWaitCertificateLength,
    sgx_ec256_signature_t* outWaitCertificateSignature
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        sp::ThrowIfNull(
            inSerializedWaitTimer,
            "Serialized timer pointer is NULL");
        sp::ThrowIfNull(
            inWaitTimerSignature,
            "Timer signature pointer is NULL");
        sp::ThrowIfNull(inBlockHash, "Block hash pointer is NULL");
        sp::ThrowIfNull(
            outSerializedWaitCertificate,
            "Serialized certificate pointer is NULL");
        sp::ThrowIfNull(
            outWaitCertificateSignature,
            "Certificate signature pointer is NULL");

        PseSession session;
        // Unseal the data
        ValidatorSignupData validatorSignupData;
        uint32_t decryptedLength = sizeof(validatorSignupData);
        sgx_status_t ret =
            sgx_unseal_data(
                reinterpret_cast<const sgx_sealed_data_t *>(
                    inSealedSignupData),
                nullptr,
                0,
                reinterpret_cast<uint8_t *>(&validatorSignupData),
                &decryptedLength);
        sp::ThrowSgxError(ret, "Failed to unseal signup data");

        sp::ThrowIf<sp::ValueError>(
            decryptedLength != sizeof(validatorSignupData),
            "Sealed signup data didn't decrypt to expected length");

        // Deserialize the wait timer so we can use pieces of it that we need
        WaitTimer waitTimer = { 0 };
        ParseWaitTimer(inSerializedWaitTimer, waitTimer);

        // Verify the signature of the serialized wait timer. The handle will
        // close automatically for us.
        Intel::SgxEcc256StateHandle eccStateHandle;

        ret = sgx_ecc256_open_context(&eccStateHandle);
        sp::ThrowSgxError(ret, "Failed to create ECC256 context");

        uint8_t signatureCheckResult;
        ret =
            sgx_ecdsa_verify(
                reinterpret_cast<const uint8_t *>(inSerializedWaitTimer),
                static_cast<uint32_t>(strlen(inSerializedWaitTimer)),
                &validatorSignupData.publicKey,
                const_cast<sgx_ec256_signature_t *>(inWaitTimerSignature),
                &signatureCheckResult,
                eccStateHandle);
        sp::ThrowSgxError(ret, "Failed to verify wait timer signature");

        if (SGX_EC_VALID != signatureCheckResult) {
            throw sp::ValueError("Wait timer signature is invalid");
        }

        // Verify that another wait timer has not been created after this
        // one and before the wait certificate has been requested.
        uint32_t sequenceId = 0;
        ret = sgx_read_monotonic_counter(
            &validatorSignupData.counterId,
            &sequenceId);
        sp::ThrowSgxError(ret, "Failed to read monotonic counter.");

        if (sequenceId != waitTimer.SequenceId) {
            Log(
                POET_LOG_ERROR,
                "WaitTimer out of sequence.  %d != %d (Attempted replay "
                "attack?)",
                sequenceId,
                waitTimer.SequenceId );
            throw
                sp::ValueError(
                    "WaitTimer out of sequence.  (Attempted replay "
                    "attack?)");
        }

        // Get the current time, give the benefit of partially elapsed seconds
        sgx_time_source_nonce_t timeNonce;
        double currentTime =
            ceil(static_cast<double>(GetCurrentTime(&timeNonce)));

        // Use only the values out of "timer", which was taken out of the
        // signed serialized wait timer.  Floor the calculation giving the
        // certificate the benefit of the doubt for partially elapsed seconds.
        double expireTime =
            floor(waitTimer.SgxRequestTime + waitTimer.Duration);

        // If the wait timer has not expired and we are not creating a wait
        // certificate for the genesis block (i.e., previous certificate ID is
        // the "null" identifier.), refuse to create the wait certificate.
        // Note that this means we are allowing the genesis block to bypass
        // the wait timer expiration
        if ((expireTime > currentTime) &&
            (NULL_IDENTIFIER != waitTimer.PreviousCertificateId)) {
            Log(
                POET_LOG_ERROR,
                "Call with unexpired timer: !(expireTime(%f) < "
                "currentTime(%f))",
                expireTime,
                currentTime);
            throw sp::ValueError("Wait timer has not expired");
        }

        // Determine the timer timed out time.  Ceil the calculation giving
        // the certificate the benefit of the doubt for partially elapsed
        // seconds.
        double timeOutTime =
            ceil(waitTimer.SgxRequestTime +
                 waitTimer.Duration       +
                 TIMER_TIMEOUT_PERIOD);

        // If the timer has timed out and we are not creating a wait
        // certificate for the genesis block, refuse to create the wait
        // certificate.  I am not certain the second check is necassary.
        if ((timeOutTime  < currentTime) &&
            (NULL_IDENTIFIER != waitTimer.PreviousCertificateId)) {
            Log(
                POET_LOG_ERROR,
                "Call with timer that has timed out: !(timeOutTime(%f) < "
                "currentTime(%f))",
                timeOutTime,
                currentTime);
            throw sp::ValueError("Wait timer has timed out");
        }

        // Create a random nonce for the wait certificate to randomize the
        // wait certificate ID and convert into a hex string so it can be
        // serialized.
        uint8_t nonce[WAIT_CERTIFICATE_NONCE_LENGTH];
        ret = sgx_read_rand(nonce, sizeof(nonce));
        sp::ThrowSgxError(ret, "Failed to generate wait certificate nonce");
        std::string nonceHexString =
            sp::BinaryToHexString(nonce, sizeof(nonce));

        // Serialize the wait certificate to a JSON string
        JsonValue waitCertValue(json_value_init_object());
        sp::ThrowIf<sp::RuntimeError>(
            !waitCertValue.value,
            "WaitCertification serialization failed on creation of JSON "
            "object.");

        JSON_Object* waitCertObject = json_value_get_object(waitCertValue);
        sp::ThrowIfNull(
            waitCertObject,
            "WaitCertification serialization failed on retrieval of JSON "
            "object.");

        // Use alphabetical order for the keys to ensure predictable
        // serialization
        JSON_Status jret =
            json_object_dotset_string(
                waitCertObject,
                "BlockHash",
                inBlockHash);
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitCertificate serialization failed on BlockHash.");
        jret =
            json_object_dotset_number(
                waitCertObject,
                "Duration",
                waitTimer.Duration);
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitCertificate serialization failed on Duration.");
        jret =
            json_object_dotset_number(
                waitCertObject,
                "LocalMean",
                waitTimer.LocalMean);
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitCertificate serialization failed on LocalMean.");
        jret =
            json_object_dotset_string(
                waitCertObject,
                "Nonce",
                nonceHexString.c_str());
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitCertificate serialization failed on Nonce.");
        jret =
            json_object_dotset_string(
                waitCertObject,
                "PreviousCertID",
                waitTimer.PreviousCertificateId.c_str());
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitCertificate serialization failed on PreviousCertID.");
        jret =
            json_object_dotset_number(
                waitCertObject,
                "RequestTime",
                waitTimer.RequestTime);
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitCertificate serialization failed on RequestTime.");
        jret =
            json_object_dotset_string(
                waitCertObject,
                "ValidatorAddress",
                waitTimer.ValidatorAddress.c_str());
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitCertificate serialization failed on ValidatorAddress.");

        size_t serializedSize = json_serialization_size(waitCertValue);
        sp::ThrowIf<sp::ValueError>(
            inSerializedWaitCertificateLength < serializedSize,
            "WaitCertificate buffer (outSerializedWaitCertificate) is too "
            "small");

        jret =
            json_serialize_to_buffer(
                waitCertValue,
                outSerializedWaitCertificate,
                inSerializedWaitCertificateLength);
        sp::ThrowIf<sp::RuntimeError>(
            jret != JSONSuccess,
            "WaitCertificate serialization failed.");

        // Now sign the serialized wait certificate using the PoET private key
        ret =
            sgx_ecdsa_sign(
                reinterpret_cast<const uint8_t *>(outSerializedWaitCertificate),
                static_cast<int32_t>(strlen(outSerializedWaitCertificate)),
                const_cast<sgx_ec256_private_t *>(
                    &validatorSignupData.privateKey),
                outWaitCertificateSignature,
                eccStateHandle);
        sp::ThrowSgxError(ret, "Failed to sign wait certificate");

        // Increment the counter to prevent creating another
        // wait certificate from the same timer.
        ret = sgx_increment_monotonic_counter(
            &validatorSignupData.counterId,
            &sequenceId);
        sp::ThrowSgxError(ret, "Failed to increment monotonic counter.");

    } catch (sp::PoetError& e) {
        Log(
            POET_LOG_ERROR,
            "Error in poet enclave(ecall_CreateWaitCertificate): %04X -- %s",
            e.error_code(),
            e.what());
        ocall_SetErrorMessage(e.what());
        result = e.error_code();
    } catch (...) {
        Log(
            POET_LOG_ERROR,
            "Unknown error in poet enclave(ecall_CreateWaitCertificate)");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // ecall_CreateWaitCertificate

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t ecall_VerifyWaitCertificate(
    const char* inSerializedWaitCertificate,
    const sgx_ec256_signature_t* inWaitCertificateSignature,
    const sgx_ec256_public_t* inPoetPublicKey
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        sp::ThrowIfNull(
            inSerializedWaitCertificate,
            "Serialized certificate pointer is NULL");
        sp::ThrowIfNull(
            inWaitCertificateSignature,
            "Certificate signature pointer is NULL");
        sp::ThrowIfNull(inPoetPublicKey, "PoET public key pointer is NULL");

        // Verify the signature of the serialized wait certificate. The handle
        // will close automatically for us.
        Intel::SgxEcc256StateHandle eccStateHandle;

        sgx_status_t ret = sgx_ecc256_open_context(&eccStateHandle);
        sp::ThrowSgxError(ret, "Failed to create ECC256 context");

        uint8_t signatureCheckResult;
        ret =
            sgx_ecdsa_verify(
                reinterpret_cast<const uint8_t *>(inSerializedWaitCertificate),
                static_cast<uint32_t>(strlen(inSerializedWaitCertificate)),
                inPoetPublicKey,
                const_cast<sgx_ec256_signature_t *>(inWaitCertificateSignature),
                &signatureCheckResult,
                eccStateHandle);
        sp::ThrowSgxError(ret, "Failed to verify wait certificate signature");
        sp::ThrowIf<sp::ValueError>(
            SGX_EC_VALID != signatureCheckResult,
            "Wait certificate signature is invalid");
    } catch (sp::PoetError& e) {
        Log(
            POET_LOG_ERROR,
            "Error in poet enclave(ecall_VerifyWaitCertificate): %04X -- %s",
            e.error_code(),
            e.what());
        ocall_SetErrorMessage(e.what());
        result = e.error_code();
    } catch (...) {
        Log(
            POET_LOG_ERROR,
            "Unknown error in poet enclave(ecall_VerifyWaitCertificate)");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // ecall_VerifyWaitCertificate

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
// XX Internal helper functions                                      XX
// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void printf(
    const char* fmt,
    ...
    )
{
    char buf[BUFSIZ] = {'\0'};
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, BUFSIZ, fmt, ap);
    va_end(ap);
    ocall_Print(buf);
} // printf

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void Log(
    int         level,
    const char* fmt,
    ...
    )
{
    char buf[BUFSIZ] = { '\0' };
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, BUFSIZ, fmt, ap);
    va_end(ap);
    ocall_Log(level, buf);
} // Log

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void CreateSignupReportData(
    const char*                 pOriginatorPublicKeyHash,
    const sgx_ec256_public_t*   pPoetPublicKey,
    sgx_report_data_t*          pReportData
    )
{
    // We will put the following in the report data SHA256(OPK_HASH|PPK).

    // WARNING - WARNING - WARNING - WARNING - WARNING - WARNING - WARNING
    //
    // If anything in this code changes the way in which the actual enclave
    // report data is represented, the corresponding code that verifies
    // the report data has to be change accordingly.
    //
    // WARNING - WARNING - WARNING - WARNING - WARNING - WARNING - WARNING

    // Canonicalize the originator public key hash string to ensure a consistent
    // format.  For capricious reasons, use upper case for hex letters.
    std::string hashString;
    std::transform(
        pOriginatorPublicKeyHash,
        pOriginatorPublicKeyHash + strlen(pOriginatorPublicKeyHash),
        std::back_inserter(hashString),
        [](char c) {
            return std::toupper(c);
        });

    // Encode the public key and make it uppercase to canonicalize it and
    // append it to the hash string.
    std::string hexString(sp::EncodePublicKey(pPoetPublicKey));
    std::transform(
        hexString.begin(),
        hexString.end(),
        std::back_inserter(hashString),
        [](char c) {
            return std::toupper(c);
        });

    // Now we put the SHA256 hash into the report data for the
    // report we will request.
    //
    // NOTE - we are putting the hash directly into the report
    // data structure because it is (64 bytes) larger than the SHA256
    // hash (32 bytes) but we zero it out first to ensure that it is
    // padded with known data.
    Zero(pReportData, sizeof(*pReportData));
    sgx_status_t ret =
        sgx_sha256_msg(
            reinterpret_cast<const uint8_t *>(hashString.c_str()),
            static_cast<uint32_t>(hashString.size()),
            reinterpret_cast<sgx_sha256_hash_t *>(pReportData));
    sp::ThrowSgxError(ret, "Failed to retrieve SHA256 hash of report data");
} // CreateSignupReportData

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
double GenerateWaitTimerDuration(
    const std::string&  validatorAddress,
    const std::string&  previousCertificateId,
    double              localMean
    )
{
    // Get the report key to use in the
    sgx_key_128bit_t    key = { 0 };
    sgx_key_request_t   key_request = { 0 };

    key_request.key_name    = SGX_KEYSELECT_SEAL;
    key_request.key_policy  = SGX_KEYPOLICY_MRENCLAVE;

    sgx_status_t ret = sgx_get_key(&key_request, &key);
    sp::ThrowSgxError(
        ret,
        "Failed to retrieve enclave key (KEYSELECT_SEAL, "
        "KEYPOLICY_MRENCLAVE).");

    std::vector<uint8_t> hashInternal;
    hashInternal.insert(
        hashInternal.end(),
        validatorAddress.begin(),
        validatorAddress.end());
    hashInternal.insert(
        hashInternal.end(),
        previousCertificateId.begin(),
        previousCertificateId.end());

    sgx_cmac_128bit_tag_t tag = { 0 };
    ret =
        sgx_rijndael128_cmac_msg(
            &key,
            &hashInternal[0],
            static_cast<uint32_t>(hashInternal.size()),
            &tag);

    sp::ThrowSgxError(ret, "Failed to seed duration generation.");

    // Normalize this value by the max value of a float/double in order to get
    // a number between 0 and 1
    double hashAsDouble =
        static_cast<double>(*(reinterpret_cast<uint64_t *>(&tag))) / ULLONG_MAX;

    // Wait duration computation with a minimum wait timer duration
    return MINIMUM_WAIT_TIME - localMean * log(hashAsDouble);
} // GenerateWaitTimerDuration

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
// currentTime contains time in seconds and timeSourceNonce contains
// nonce associate with the time. The caller should compare timeSourceNonce
// against the value returned from the previous call of this API if it needs
// to calculate the time passed between two readings of the  Trusted Timer.
// If the timeSourceNonce of the two readings do not match, the difference
// between the two readings does not necessarily reflect time passed.

sgx_time_t GetCurrentTime(
    sgx_time_source_nonce_t*    pNonce
    )
{
    sgx_time_t              currentTime;
    sgx_time_source_nonce_t timeSourceNonce;

    if (!pNonce) {
        pNonce = &timeSourceNonce;
    }

    sgx_status_t ret = sgx_get_trusted_time(&currentTime, pNonce);
    sp::ThrowSgxError(ret, "Failed to get trusted time(GetCurrentTime)");

    return currentTime;
} // GetCurrentTime

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void ParseWaitTimer(
    const char* pSerializedWaitTimer,
    WaitTimer&  waitTimer
    )
{
    JsonValue parsed(json_parse_string(pSerializedWaitTimer));
    sp::ThrowIf<sp::ValueError>(
        !parsed.value,
        "Failed to parse WaitTimer");

    JSON_Object* pObject = json_value_get_object(parsed);
    const char* pStr = nullptr;

    waitTimer.Duration = json_object_dotget_number(pObject, "Duration");
    waitTimer.LocalMean = json_object_dotget_number(pObject, "LocalMean");

    pStr = json_object_dotget_string(pObject, "PreviousCertID");
    sp::ThrowIf<sp::ValueError>(
        !pStr,
        "Parse WaitTimer failed to retrieve PreviousCertID");
    waitTimer.PreviousCertificateId.assign(pStr);

    waitTimer.RequestTime = json_object_dotget_number(pObject, "RequestTime");
    waitTimer.SequenceId =
        static_cast<uint32_t>(
            json_object_dotget_number(pObject, "SequenceId"));
    waitTimer.SgxRequestTime =
        json_object_dotget_number(pObject, "SgxRequestTime");

    pStr = json_object_dotget_string(pObject, "ValidatorAddress");
    sp::ThrowIf<sp::ValueError>(
        !pStr,
        "Parse WaitTimer failed to retrieve ValidatorAddress");
    waitTimer.ValidatorAddress.assign(pStr);
} // ParseWaitTimer

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
size_t CalculateSealedSignupDataSize()
{
    return sgx_calc_sealed_data_size(0, sizeof(ValidatorSignupData));
} // CalculateSealedSignupDataSize

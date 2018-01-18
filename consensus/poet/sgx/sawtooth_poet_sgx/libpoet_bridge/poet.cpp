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

#include "poet.h"
#include "log.h"
#include "utils.h"
#include "hex_string.h"
#include "enclave.h"
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string.h>
#include <iterator>
#include <algorithm>
#include "sgx_ukey_exchange.h" /*To call untrusted key exchange library i.e., sgx_ra_get_msg1() and sgx_ra_proc_msg2() */

#include "error.h"

#include "zero.h"
#include "public_key_util.h"

#define CERTIFICATE_ID_LENGTH 16
#define MAX_ADDRESS_LENGTH 66
#define MIN_ADDRESS_LENGTH 26

namespace sp = sawtooth::poet;

// This macro calculates the length of the actual data portion of the
// base 64 encoding of a buffer with x bytes PLUS the additional byte
// needed for the string terminator.
#define BASE64_SIZE(x) (static_cast<size_t>(((((x) - 1) / 3) * 4 + 4) + 1))

sp::Enclave g_Enclave;
static bool g_IsInitialized = false;
static std::string g_LastError;

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
// XX Declaration of static helper functions                         XX
// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

static void Poet_SetLastError(
    const char* msg
    );

static void Poet_EncodeSignature(
    char* outEncodedSignature,
    size_t inEncodedSignatureLength,
    const sgx_ec256_signature_t* inSignature
    );

static void Poet_DecodeSignature(
    sgx_ec256_signature_t *outSignature,
    const char* inEncodedSignature
    );

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
// XX External interface                                             XX
// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
int Poet_IsSgxSimulator()
{
#if defined(SGX_SIMULATOR)
    return 1;
#else // defined(SGX_SIMULATOR)
    return 0;
#endif // defined(SGX_SIMULATOR)
} // Poet_IsSgxSimulator

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t Poet_GetLastErrorMessage(
    char* outMessage,
    size_t inMessageLength
    )
{
    poet_err_t ret = POET_SUCCESS;
    if (outMessage) {
        strncpy_s(
            outMessage,
            inMessageLength,
            g_LastError.c_str(),
            g_LastError.length());
    }

    return ret;
} // Poet_GetLastErrorMessage

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t Poet_Initialize(
    const char* inDataDirectory,
    const char* inPathToEnclave,
    const char* inSpid,
    poet_log_t logFunction
    )
{
    poet_err_t ret = POET_SUCCESS;

    try {
        if (!g_IsInitialized)
        {
            sp::ThrowIfNull(inDataDirectory, "Data directory string is NULL");
            sp::ThrowIfNull(inPathToEnclave, "Enclave path string is NULL");
            sp::ThrowIfNull(inSpid, "SPID buffer is NULL");

            sp::SetLogFunction(logFunction);
            g_Enclave.SetSpid(inSpid);
            g_Enclave.SetDataDirectory(inDataDirectory);
            g_Enclave.Load(inPathToEnclave);
            g_IsInitialized = true;
        }
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        ret = e.error_code();
    } catch(std::exception& e) {
        Poet_SetLastError(e.what());
        ret = POET_ERR_UNKNOWN;
    } catch(...) {
        Poet_SetLastError("Unexpected exception");
        ret = POET_ERR_UNKNOWN;
    }

    return ret;
} // Poet_Initialize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t Poet_Terminate()
{
    // Unload the enclave
    poet_err_t ret = POET_SUCCESS;

    try {
        if (g_IsInitialized) {
            g_Enclave.Unload();
            g_IsInitialized = false;
        }
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        ret = e.error_code();
    } catch (std::exception& e) {
        Poet_SetLastError(e.what());
        ret = POET_ERR_UNKNOWN;
    } catch (...) {
        Poet_SetLastError("Unexpected exception");
        ret = POET_ERR_UNKNOWN;
    }

    return ret;
} // Poet_Terminate

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC size_t Poet_GetEpidGroupSize()
{
    return HEX_STRING_SIZE(sizeof(sgx_epid_group_id_t));
} // Poet_GetEpidGroupSize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC size_t Poet_GetEnclaveMeasurementSize()
{
    return
        HEX_STRING_SIZE(
            sizeof((static_cast<sgx_measurement_t *>(nullptr))->m));
} // Poet_GetEnclaveMeasurementSize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC size_t Poet_GetEnclaveBasenameSize()
{
    return
        HEX_STRING_SIZE(
            sizeof((static_cast<sgx_quote_t *>(nullptr))->basename));
} // Poet_GetEnclaveBasenameSize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC size_t Poet_GetEnclavePseManifestHashSize()
{
    return HEX_STRING_SIZE(sizeof(sgx_sha256_hash_t));
} // Poet_GetEnclavePseManifestHashSize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC size_t Poet_GetWaitTimerSize()
{
    return 2*1024; // Empirically these are big enough
}

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC size_t Poet_GetWaitCertificateSize()
{
    return 2*1024; // Empirically these are big enough
}

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC size_t Poet_GetSignatureSize()
{
    // We encode the components of the signature separately to avoid
    // potential for struct alignment issues
    return
        BASE64_SIZE(
            sizeof(static_cast<sgx_ec256_signature_t *>(nullptr)->x) +
            sizeof(static_cast<sgx_ec256_signature_t *>(nullptr)->y));
}

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC size_t Poet_GetPublicKeySize()
{
    return sp::EncodedPublicKeySize();
} // Poet_GetPublicKeySize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC size_t Poet_GetPseManifestSize()
{
    return BASE64_SIZE(sizeof(sgx_ps_sec_prop_desc_t));
} // Poet_GetPseManifestSize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC size_t Poet_GetEnclaveQuoteSize()
{
    return BASE64_SIZE(g_Enclave.GetQuoteSize());
} // Poet_GetEnclaveQuoteSize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC size_t Poet_GetSealedSignupDataSize()
{
    return BASE64_SIZE(g_Enclave.GetSealedSignupDataSize());
} // Poet_GetSealedSignupDataSize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t Poet_GetEpidGroup(
    char* outEpidGroup,
    size_t inEpidGroupLength
    )
{
     poet_err_t ret = POET_SUCCESS;

     try {
        sp::ThrowIfNull(outEpidGroup, "NULL outEpidGroup");
        sp::ThrowIf<sp::ValueError>(
           inEpidGroupLength < Poet_GetEpidGroupSize(),
           "EPID group buffer is too small");

        // Get the EPID group from the enclave and convert it to big endian
        sgx_epid_group_id_t epidGroup;
        g_Enclave.GetEpidGroup(epidGroup);

        std::reverse(epidGroup, epidGroup + sizeof(epidGroup));

        // Convert the binary data to a hex string and copy it to the caller's
        // buffer
        std::string hexString =
            sp::BinaryToHexString(epidGroup, sizeof(epidGroup));
        strncpy_s(
           outEpidGroup,
           inEpidGroupLength,
           hexString.c_str(),
           hexString.length());
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        ret = e.error_code();
    } catch (std::exception& e) {
        Poet_SetLastError(e.what());
        ret = POET_ERR_UNKNOWN;
    } catch (...) {
        Poet_SetLastError("Unexpected exception");
        ret = POET_ERR_UNKNOWN;
    }

    return ret;
} // Poet_GetEpidGroup

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t Poet_GetEnclaveCharacteristics(
    char* outMrEnclave,
    size_t inMrEnclaveLength,
    char* outEnclaveBasename,
    size_t inEnclaveBasenameLength,
    char* outEnclavePseManifestHash,
    size_t inEnclavePseManifestHashSize
    )
{
    poet_err_t ret = POET_SUCCESS;

    try {
        sp::ThrowIfNull(outMrEnclave, "NULL outMrEnclave");
        sp::ThrowIf<sp::ValueError>(
           inMrEnclaveLength < Poet_GetEnclaveMeasurementSize(),
           "Enclave measurement buffer is too small");
        sp::ThrowIfNull(outEnclaveBasename, "NULL outEnclaveBasename");
        sp::ThrowIf<sp::ValueError>(
           inEnclaveBasenameLength < Poet_GetEnclaveBasenameSize(),
           "Enclave basename buffer is too small");
        sp::ThrowIfNull(
            outEnclavePseManifestHash,
            "NULL outEnclavePseManifestHash");
        sp::ThrowIf<sp::ValueError>(
           inEnclavePseManifestHashSize < Poet_GetEnclavePseManifestHashSize(),
           "Enclave PSE manifest hash buffer is too small");

        // Get the enclave characteristics and then convert the binary data to
        // hex strings and copy them to the caller's buffers.
        sgx_measurement_t enclaveMeasurement;
        sgx_basename_t enclaveBasename;
        sgx_sha256_hash_t enclavePseManifestHash;

        g_Enclave.GetEnclaveCharacteristics(
            &enclaveMeasurement,
            &enclaveBasename,
            &enclavePseManifestHash);

        std::string hexString =
            sp::BinaryToHexString(
                enclaveMeasurement.m,
                sizeof(enclaveMeasurement.m));
        strncpy_s(
           outMrEnclave,
           inMrEnclaveLength,
           hexString.c_str(),
           hexString.length());

        hexString =
            sp::BinaryToHexString(
                enclaveBasename.name,
                sizeof(enclaveBasename.name));
        strncpy_s(
           outEnclaveBasename,
           inEnclaveBasenameLength,
           hexString.c_str(),
           hexString.length());

        hexString =
            sp::BinaryToHexString(
                enclavePseManifestHash,
                sizeof(enclavePseManifestHash));
        strncpy_s(
           outEnclavePseManifestHash,
           inEnclavePseManifestHashSize,
           hexString.c_str(),
           hexString.length());
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        ret = e.error_code();
    } catch (std::exception& e) {
        Poet_SetLastError(e.what());
        ret = POET_ERR_UNKNOWN;
    } catch (...) {
        Poet_SetLastError("Unexpected exception");
        ret = POET_ERR_UNKNOWN;
    }

    return ret;
} // Poet_GetEnclaveCharacteristics

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t Poet_SetSignatureRevocationList(
    const char* inSignatureRevocationList
    )
{
    poet_err_t ret = POET_SUCCESS;

    try {
        sp::ThrowIfNull(
            inSignatureRevocationList,
            "NULL inSignatureRevocationList");

        g_Enclave.SetSignatureRevocationList(inSignatureRevocationList);
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        ret = e.error_code();
    } catch (std::exception& e) {
        Poet_SetLastError(e.what());
        ret = POET_ERR_UNKNOWN;
    } catch (...) {
        Poet_SetLastError("Unexpected exception");
        ret = POET_ERR_UNKNOWN;
    }

    return ret;
} // Poet_SetSignatureRevocationList

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC poet_err_t Poet_CreateSignupData(
    const char* inOriginatorPublicKeyHash,
    char* outPoetPublicKey,
    size_t inPoetPublicKeySize,
    char* outPseManifest,
    size_t inPseManifestSize,
    char* outEnclaveQuote,
    size_t inEnclaveQuoteSize,
    char* outSealedSignupData,
    size_t inSealedSignupDataSize
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        // validate params
        sp::ThrowIfNull(inOriginatorPublicKeyHash, "NULL inOriginatorPublicKeyHash");
        sp::ThrowIfNull(outPoetPublicKey, "NULL outPoetPublicKey");
        sp::ThrowIf<sp::ValueError>(
            inPoetPublicKeySize < Poet_GetPublicKeySize(),
            "Public key buffer too small (outPoetPublicKey)");
        sp::ThrowIfNull(outPseManifest, "NULL outPseManifest");
        sp::ThrowIf<sp::ValueError>(
            inPseManifestSize < Poet_GetPseManifestSize(),
            "PSE manifest buffer too small (outPseManifest)");
        sp::ThrowIfNull(outEnclaveQuote, "NULL outEnclaveQuote");
        sp::ThrowIf<sp::ValueError>(
            inEnclaveQuoteSize < Poet_GetEnclaveQuoteSize(),
            "Enclave quote buffer too small (outEnclaveQuote)");
        sp::ThrowIfNull(outSealedSignupData, "NULL outSealedSignupData");
        sp::ThrowIf<sp::ValueError>(
            inSealedSignupDataSize < Poet_GetSealedSignupDataSize(),
            "Sealed signup data buffer too small (inSealedSignupDataSize)");

        // Clear out the buffers
        Zero(outPoetPublicKey, inPoetPublicKeySize);
        Zero(outPseManifest, inPseManifestSize);
        Zero(outEnclaveQuote, inEnclaveQuoteSize);
        Zero(outSealedSignupData, inSealedSignupDataSize);

        // Have the enclave create the signup data
        sgx_ec256_public_t poetPublicKey = {0};
        sp::Enclave::buffer_t enclaveQuote;
        sgx_ps_sec_prop_desc_t pseManifest = {0};
        sp::Enclave::buffer_t sealedSignupData;

        g_Enclave.CreateSignupData(
            inOriginatorPublicKeyHash,
            &poetPublicKey,
            enclaveQuote,
            &pseManifest,
            sealedSignupData);

        // Encode and copy the data that is to be returned to the caller
        std::string encodedPublicKey(sp::EncodePublicKey(&poetPublicKey));
        strncpy_s(
            outPoetPublicKey,
            inPoetPublicKeySize,
            encodedPublicKey.c_str(),
            encodedPublicKey.length());
        sp::EncodeB64(outPseManifest, inPseManifestSize, &pseManifest);
        sp::EncodeB64(outEnclaveQuote, inEnclaveQuoteSize, enclaveQuote);
        sp::EncodeB64(
            outSealedSignupData,
            inSealedSignupDataSize,
            sealedSignupData);
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        result = e.error_code();
    } catch (std::exception& e) {
        Poet_SetLastError(e.what());
        result = POET_ERR_UNKNOWN;
    } catch (...) {
        Poet_SetLastError("Unexpected exception");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // Poet_CreateSignupData

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t Poet_UnsealSignupData(
    const char* inSealedSignupData,
    char* outPoetPublicKey,
    size_t inPoetPublicKeySize
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        // validate params
        sp::ThrowIfNull(
            inSealedSignupData,
            "NULL inSealedSignupData");
        sp::ThrowIfNull(outPoetPublicKey, "NULL outPoetPublicKey");
        sp::ThrowIf<sp::ValueError>(
            inPoetPublicKeySize < Poet_GetPublicKeySize(),
            "Public key buffer too small (outPoetPublicKey)");

        // Clear out the buffers
        Zero(outPoetPublicKey, inPoetPublicKeySize);

        // Decode the sealed data before sending it down
        std::vector<uint8_t> sealedSignupData;
        sp::DecodeB64(sealedSignupData, inSealedSignupData);

        // Have the enclave unseal the signup data
        sgx_ec256_public_t  poetPublicKey = {0};

        g_Enclave.UnsealSignupData(sealedSignupData, &poetPublicKey);

        // Encode and copy the data that is to be returned to the caller
        std::string encodedPublicKey(sp::EncodePublicKey(&poetPublicKey));
        strncpy_s(
            outPoetPublicKey,
            inPoetPublicKeySize,
            encodedPublicKey.c_str(),
            encodedPublicKey.length());
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        result = e.error_code();
    } catch (std::exception& e) {
        Poet_SetLastError(e.what());
        result = POET_ERR_UNKNOWN;
    } catch (...) {
        Poet_SetLastError("Unexpected exception");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // Poet_UnsealSignupData

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t Poet_ReleaseSignupData(
    const char* inSealedSignupData
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        // validate params
        sp::ThrowIfNull(
            inSealedSignupData,
            "NULL inSealedSignupData");

        // Decode the sealed data before sending it down
        std::vector<uint8_t> sealedSignupData;
        sp::DecodeB64(sealedSignupData, inSealedSignupData);

        // Have the enclave release the signup data
        g_Enclave.ReleaseSignupData(sealedSignupData);
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        result = e.error_code();
    } catch (std::exception& e) {
        Poet_SetLastError(e.what());
        result = POET_ERR_UNKNOWN;
    } catch (...) {
        Poet_SetLastError("Unexpected exception");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // Poet_ReleaseSignupData

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t Poet_VerifySignupInfo(
    const char* inOriginatorPublicKeyHash,
    const char* inPoetPublicKey,
    const char* inEnclaveQuote,
    const char* inPseManifestHash
    )
{
    poet_err_t result = POET_SUCCESS;

    try {
        // validate params
        sp::ThrowIfNull(inOriginatorPublicKeyHash, "NULL inOriginatorPublicKeyHash");
        sp::ThrowIfNull(inPoetPublicKey, "NULL inPoetPublicKey");
        sp::ThrowIfNull(inEnclaveQuote, "NULL inEnclaveQuote");
        sp::ThrowIfNull(inPseManifestHash,  "NULL inPseManifestHash");

        // Take the encoded public key and decode it
        sgx_ec256_public_t poetPublicKey;
        sp::DecodePublicKey(&poetPublicKey, inPoetPublicKey);

        // Take the encoded enclave quote and turn it into a sgx_quote_t.  We
        // decode into a vector because quote buffers are variable size.
        std::vector<uint8_t> enclaveQuoteBuffer;
        sp::DecodeB64(enclaveQuoteBuffer, inEnclaveQuote);

        // Take the hex encoded PSE manifest hash and decode it
        sgx_sha256_hash_t pseManifestHash;
        sp::HexStringToBinary(
            reinterpret_cast<uint8_t *>(&pseManifestHash),
            sizeof(pseManifestHash),
            inPseManifestHash);

        // Now let the enclave take over
        g_Enclave.VerifySignupInfo(
            inOriginatorPublicKeyHash,
            &poetPublicKey,
            reinterpret_cast<sgx_quote_t *>(&enclaveQuoteBuffer[0]),
            enclaveQuoteBuffer.size(),
            &pseManifestHash);
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        result = e.error_code();
    } catch (std::exception& e) {
        Poet_SetLastError(e.what());
        result = POET_ERR_UNKNOWN;
    } catch (...) {
        Poet_SetLastError("Unexpected exception");
        result = POET_ERR_UNKNOWN;
    }

    return result;
} // Poet_VerifySignupInfo

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t Poet_CreateWaitTimer(
    const char* inSealedSignupData,
    const char* inValidatorAddress,
    const char* inPreviousCertificateId,
    double inRequestTime,
    double inLocalMean,
    char* outSerializedWaitTimer,
    size_t inSerializedTimerLength,
    char* outWaitTimerSignature,
    size_t inWaitTimerSignatureLength
    )
{
    poet_err_t ret = POET_SUCCESS;

    try {
        // validate params
        sp::ThrowIfNull(inSealedSignupData, "NULL SealedSignupData");
        sp::ThrowIfNull(inValidatorAddress, "NULL ValidatorAddress");
        sp::ThrowIfNull(inPreviousCertificateId, "NULL inPreviousCertificateId");
        sp::ThrowIfNull(outSerializedWaitTimer, "NULL outSerializedWaitTimer");
        sp::ThrowIfNull(outWaitTimerSignature, "NULL outWaitTimerSignature");
        size_t addressLength = strlen(inValidatorAddress);
        sp::ThrowIf<sp::ValueError>(
             addressLength > MAX_ADDRESS_LENGTH
             || addressLength < MIN_ADDRESS_LENGTH,
            "Invalid Validator Address"
            );
        sp::ThrowIf<sp::ValueError>(
            inSerializedTimerLength < Poet_GetWaitTimerSize(),
            "WaitTimer buffer to small (outSerializedWaitTimer)"
            );
        sp::ThrowIf<sp::ValueError>(
            inWaitTimerSignatureLength < Poet_GetSignatureSize(),
            "Signature buffer to small (outWaitTimerSignature)"
            );
        sp::ThrowIf<sp::ValueError>(
            inLocalMean <= 0.0,
            "Invalid local mean time"
            );
        sp::ThrowIf<sp::ValueError>(
            strlen(inPreviousCertificateId) != CERTIFICATE_ID_LENGTH,
            "Invalid Previous CertificateId"
            );

        Zero(outSerializedWaitTimer, inSerializedTimerLength);
        Zero(outWaitTimerSignature, inWaitTimerSignatureLength);

        // Decode the sealed data before sending it down
        std::vector<uint8_t> sealedSignupData;
        sp::DecodeB64(sealedSignupData, inSealedSignupData);

        sgx_ec256_signature_t waitTimerSignature = { 0 };
        g_Enclave.CreateWaitTimer(
            sealedSignupData,
            inValidatorAddress,
            inPreviousCertificateId,
            inRequestTime,
            inLocalMean,
            outSerializedWaitTimer,
            inSerializedTimerLength,
            &waitTimerSignature);

        // Encode the timer signature returned
        Poet_EncodeSignature(
            outWaitTimerSignature,
            inWaitTimerSignatureLength,
            &waitTimerSignature);
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        ret = e.error_code();
    } catch (std::exception& e) {
        Poet_SetLastError(e.what());
        ret = POET_ERR_UNKNOWN;
    } catch (...) {
        Poet_SetLastError("Unexpected exception");
        ret = POET_ERR_UNKNOWN;
    }

    return ret;
} // Poet_CreateWaitTimer

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
poet_err_t Poet_CreateWaitCertificate(
    const char* inSealedSignupData,
    const char* inSerializedWaitTimer,
    const char* inWaitTimerSignature,
    const char* inBlockHash,
    char* outSerializedWaitCertificate,
    size_t inSerializedWaitCertificateLength,
    char* outWaitCertificateSignature,
    size_t inWaitCertificateSignatureLength
    )
{
    poet_err_t ret = POET_SUCCESS;
    try {
        // validate params
        sp::ThrowIfNull(inSealedSignupData, "NULL SealedSignupData");
        sp::ThrowIfNull(inSerializedWaitTimer, "NULL inSerializedWaitTimer");
        sp::ThrowIfNull(inWaitTimerSignature, "NULL inWaitTimerSignature");
        sp::ThrowIfNull(inBlockHash, "NULL inBlockHash");
        sp::ThrowIfNull(
            outSerializedWaitCertificate,
            "NULL outSerializedWaitCertificate");
        sp::ThrowIfNull(
            outWaitCertificateSignature,
            "NULL outWaitCertificateSignature");
        sp::ThrowIf<sp::ValueError>(
            inSerializedWaitCertificateLength < Poet_GetWaitCertificateSize(),
            "WaitCertificate buffer to small (outSerializedWaitCertificate)"
            );
        sp::ThrowIf<sp::ValueError>(
            inWaitCertificateSignatureLength < Poet_GetSignatureSize(),
            "Signature buffer to small (outWaitCertificateSignature)"
            );

        Zero(outSerializedWaitCertificate, inSerializedWaitCertificateLength);
        Zero(outWaitCertificateSignature, inWaitCertificateSignatureLength);

        // Decode the sealed data before sending it down
        std::vector<uint8_t> sealedSignupData;
        sp::DecodeB64(sealedSignupData, inSealedSignupData);

        sgx_ec256_signature_t waitTimerSignature;
        sgx_ec256_signature_t waitCertificateSignature;

        // Take the encoded wait timer signature and convert into something
        // that is more convenient to use internally
        Poet_DecodeSignature(&waitTimerSignature, inWaitTimerSignature);

        g_Enclave.CreateWaitCertificate(
            sealedSignupData,
            inSerializedWaitTimer,
            &waitTimerSignature,
            inBlockHash,
            outSerializedWaitCertificate,
            inSerializedWaitCertificateLength,
            &waitCertificateSignature);

        // Encode the certificate signature returned
        Poet_EncodeSignature(
            outWaitCertificateSignature,
            inWaitCertificateSignatureLength,
            &waitCertificateSignature);
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        ret = e.error_code();
    } catch (std::exception& e) {
        Poet_SetLastError(e.what());
        ret = POET_ERR_UNKNOWN;
    } catch (...) {
        Poet_SetLastError("Unexpected exception");
        ret = POET_ERR_UNKNOWN;
    }

    return ret;
} // Poet_CreateWaitCertificate

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
POET_FUNC poet_err_t Poet_VerifyWaitCertificate(
    const char* inSerializedWaitCertificate,
    const char* inWaitCertificateSignature,
    const char* inPoetPublicKey
    )
{
    poet_err_t ret = POET_SUCCESS;

    try {
        // validate params
        sp::ThrowIfNull(
            inSerializedWaitCertificate,
            "NULL inSerializedWaitCertificate");
        sp::ThrowIfNull(
            inWaitCertificateSignature,
            "NULL inWaitCertificateSignature");
        sp::ThrowIfNull(inPoetPublicKey, "NULL inPoetPublicKey");

        sgx_ec256_signature_t waitCertificateSignature;
        sgx_ec256_public_t poetPublicKey;

        // Take the encoded wait certificate signature and PoET public keys and
        // convert them into something that is more convenient to use internally
        Poet_DecodeSignature(
            &waitCertificateSignature,
            inWaitCertificateSignature);
        sp::DecodePublicKey(&poetPublicKey, inPoetPublicKey);

        g_Enclave.VerifyWaitCertificate(
            inSerializedWaitCertificate,
            &waitCertificateSignature,
            &poetPublicKey);
    } catch (sp::PoetError& e) {
        Poet_SetLastError(e.what());
        ret = e.error_code();
    } catch (std::exception& e) {
        Poet_SetLastError(e.what());
        ret = POET_ERR_UNKNOWN;
    } catch (...) {
        Poet_SetLastError("Unexpected exception");
        ret = POET_ERR_UNKNOWN;
    }

    return ret;
} // Poet_VerifyWaitCertificate

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
// XX Internal helper functions                                      XX
// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void Poet_SetLastError(
    const char* msg
    )
{
    if (msg) {
        g_LastError = msg;
    }
    else {
        g_LastError = "No error description";
    }
} // Poet_SetLastError

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void Poet_EncodeSignature(
    char* outEncodedSignature,
    size_t inEncodedSignatureLength,
    const sgx_ec256_signature_t* inSignature
    )
{
    // NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE
    //
    // Before converting the signature to a base 64 string we are going to
    // reverse the signature x and y components as it appears that these large
    // integers seem (I say seem as I don't have access to source code) to be
    // stored in the arrays in little endian.  Therefore, we are going to
    // reverse them so that they are in big endian.
    //
    // NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE

    // We know that the buffer will be no bigger than
    // sizeof(*inSignature) because of potential padding
    std::vector<uint8_t> bigEndianBuffer;
    bigEndianBuffer.reserve(sizeof(*inSignature));

    // Copy the x and y components of the public key into the the buffer,
    // reversing the order of bytes as we do so.
    std::copy(
        std::reverse_iterator<const uint8_t *>(
            reinterpret_cast<const uint8_t *>(inSignature->x) +
            sizeof(inSignature->x)),
        std::reverse_iterator<const uint8_t *>(
            reinterpret_cast<const uint8_t *>(inSignature->x)),
        std::back_inserter(bigEndianBuffer));
    std::copy(
        std::reverse_iterator<const uint8_t *>(
            reinterpret_cast<const uint8_t *>(inSignature->y) +
            sizeof(inSignature->y)),
        std::reverse_iterator<const uint8_t *>(
            reinterpret_cast<const uint8_t *>(inSignature->y)),
        std::back_inserter(bigEndianBuffer));

    // Now convert the signature components to base 64 into the caller's buffer
    sp::EncodeB64(
        outEncodedSignature,
        inEncodedSignatureLength,
        bigEndianBuffer);
} // Poet_EncodeSignature

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void Poet_DecodeSignature(
    sgx_ec256_signature_t *outSignature,
    const char* inEncodedSignature
    )
{
    // First convert the base 64 string to a buffer of bytes
    std::vector<uint8_t> bigEndianBuffer;
    sp::DecodeB64(bigEndianBuffer, inEncodedSignature);

    // NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE
    //
    // After converting the base 64 string to a signature we are going to
    // reverse the signature x and y components as it appears that these large
    // integers seem (I say seem as I don't have access to source code) to be
    // stored in the arrays in little endian.  Therefore, we are going to
    // reverse them from the big endian format we used when we encoded it.
    //
    // NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE

    // Copy the contents of the buffer into the x and y components of
    // the signature, reversing the order of the bytes as we do so.
    std::copy(
        std::reverse_iterator<uint8_t *>(
            &bigEndianBuffer[0] + sizeof(outSignature->x)),
        std::reverse_iterator<uint8_t *>(&bigEndianBuffer[0]),
        reinterpret_cast<uint8_t *>(outSignature->x));
    std::copy(
        std::reverse_iterator<uint8_t *>(
            &bigEndianBuffer[sizeof(outSignature->x)] +
            sizeof(outSignature->y)),
        std::reverse_iterator<uint8_t *>(
            &bigEndianBuffer[sizeof(outSignature->x)]),
        reinterpret_cast<uint8_t *>(outSignature->y));
} // Poet_DecodeSignature

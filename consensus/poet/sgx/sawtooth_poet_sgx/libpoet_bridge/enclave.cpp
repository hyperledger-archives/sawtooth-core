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

#include <iostream>
#include <sstream>
#include <stdexcept>

#include <sgx_uae_service.h>
#include <sgx_ukey_exchange.h>
#include "sgx_support.h"
#include "platform_support.h"

#include "enclave.h"

#include "poet_enclave_u.h"
#include "log.h"
#include "error.h"
#include "zero.h"
#include "hex_string.h"

extern std::string g_enclaveError;

namespace sawtooth {
    namespace poet {

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        inline sgx_status_t ConvertPoetErrorStatus(
            sgx_status_t ret,
            poet_err_t poetRet)
        {
            // If the SGX code is successs and the PoET error code is
            // "busy", then convert to appropriate value.
            if ((SGX_SUCCESS == ret) &&
                (POET_ERR_SYSTEM_BUSY == poetRet)) {
                return SGX_ERROR_DEVICE_BUSY;
            }

            return ret;
        } // ConvertPoetErrorStatus

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        // XX External interface                                     XX
        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        Enclave::Enclave() :
            enclaveId(0),
            sealedSignupDataSize(0)
        {
            uint32_t size;
            sgx_status_t ret = sgx_calc_quote_size(nullptr, 0, &size);
            ThrowSgxError(ret, "Failed to get SGX quote size.");
            this->quoteSize = size;
        } // Enclave::Enclave

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        Enclave::~Enclave()
        {
            try {
                this->Unload();
            } catch (PoetError& e) {
                Log(
                    POET_LOG_ERROR,
                    "Error unloading poet enclave: %04X -- %s",
                    e.error_code(),
                    e.what());
            } catch (...) {
                Log(
                    POET_LOG_ERROR,
                    "Unknown error unloading poet enclave");
            }
        } // Enclave::~Enclave

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::Load(
            const std::string& inEnclaveFilePath
            )
        {
            ThrowIf<ValueError>(inEnclaveFilePath.empty() ||
                inEnclaveFilePath.length() > MAXIMUM_PATH_LENGTH,
                "Invalid enclave path.");
            this->Unload();
            this->enclaveFilePath = inEnclaveFilePath;
            this->LoadEnclave();
        } // Enclave::Load

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::Unload()
        {
            if (this->enclaveId) {
                // no power or busy retries here....
                // we don't want to reinitialize just to shutdown.
                sgx_destroy_enclave(this->enclaveId);
                this->enclaveId = 0;
            }
        } // Enclave::Unload

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::GetEpidGroup(
            sgx_epid_group_id_t outEpidGroup
            )
        {
            sgx_ra_msg1_t remoteAttestationMessage1;

            sgx_status_t ret =
                this->CallSgx(
                    [this,
                     &remoteAttestationMessage1] () {
                    return
                        sgx_ra_get_msg1(
                            this->raContext,
                            this->enclaveId,
                            sgx_ra_get_ga,
                            &remoteAttestationMessage1);
                });
            ThrowSgxError(
                ret,
                "Failed to retrieve remote attestation message (EPID group "
                "ID)");

            memcpy_s(
                outEpidGroup,
                sizeof(sgx_epid_group_id_t),
                remoteAttestationMessage1.gid,
                sizeof(sgx_epid_group_id_t));
        } // Enclave::GetEpidGroup

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::GetEnclaveCharacteristics(
            sgx_measurement_t* outEnclaveMeasurement,
            sgx_basename_t* outEnclaveBasename,
            sgx_sha256_hash_t* outEnclavePseManifestHash
            )
        {
            ThrowIfNull(
                outEnclaveMeasurement,
                "Enclave measurement pointer is NULL");
            ThrowIfNull(
                outEnclaveBasename,
                "Enclave basename pointer is NULL");
            ThrowIfNull(
                outEnclavePseManifestHash,
                "Enclave PSE manifest hash pointer is NULL");

            Zero(outEnclaveMeasurement, sizeof(*outEnclaveMeasurement));
            Zero(outEnclaveBasename, sizeof(*outEnclaveBasename));
            Zero(outEnclavePseManifestHash, sizeof(*outEnclavePseManifestHash));

            // We can get the enclave's measurement (i.e., mr_enclave) and
            // basename only by getting a quote.  To do that, we need to first
            // generate a report.

            // Initialize a quote
            sgx_target_info_t targetInfo = { 0 };
            sgx_epid_group_id_t gid = { 0 };

            sgx_status_t ret = this->CallSgx([&targetInfo, &gid] () {
                return sgx_init_quote(&targetInfo, &gid);
            });
            ThrowSgxError(ret, "Failed to initialize enclave quote");

            // Now retrieve a fake enclave report so that we can later
            // create a quote from it.  We need to the quote so that we can
            // get some of the information (basename and mr_enclave,
            // specifically) being requested.
            sgx_report_t enclaveReport = { 0 };
            poet_err_t poetRet = POET_SUCCESS;
            ret =
                this->CallSgx(
                    [this,
                     &poetRet,
                     &targetInfo,
                     &enclaveReport] () {
                    sgx_status_t ret =
                        ecall_CreateErsatzEnclaveReport(
                            this->enclaveId,
                            &poetRet,
                            &targetInfo,
                            &enclaveReport);
                    return ConvertPoetErrorStatus(ret, poetRet);
                });
            ThrowSgxError(
                ret,
                "Failed to retrieve ersatz enclave report");
            this->ThrowPoetError(poetRet);

            // Properly size a buffer to receive an enclave quote and then
            // retrieve it.  The enclave quote contains the basename.
            buffer_t enclaveQuoteBuffer(this->quoteSize);
            sgx_quote_t* enclaveQuote =
                reinterpret_cast<sgx_quote_t *>(&enclaveQuoteBuffer[0]);
            const uint8_t* pRevocationList = nullptr;
            if (this->signatureRevocationList.size()) {
                pRevocationList =
                    reinterpret_cast<const uint8_t *>(
                        this->signatureRevocationList.c_str());
            }

            ret =
                this->CallSgx(
                    [this,
                     &enclaveReport,
                     pRevocationList,
                     &enclaveQuoteBuffer] () {
                    return
                        sgx_get_quote(
                            &enclaveReport,
                            SGX_LINKABLE_SIGNATURE,
                            &this->spid,
                            nullptr,
                            pRevocationList,
                            static_cast<uint32_t>(
                                this->signatureRevocationList.size()),
                            nullptr,
                            reinterpret_cast<sgx_quote_t *>(
                                &enclaveQuoteBuffer[0]),
                            static_cast<uint32_t>(enclaveQuoteBuffer.size()));
                });
            ThrowSgxError(
                ret,
                "Failed to create linkable quote for enclave report");

            // Now get the PSE manifest hash and let the function copy it
            // directly into the caller's buffer
            ret =
                this->CallSgx(
                    [this,
                     &poetRet,
                     outEnclavePseManifestHash] () {
                    sgx_status_t ret =
                        ecall_GetPseManifestHash(
                            this->enclaveId,
                            &poetRet,
                            outEnclavePseManifestHash);
                    return ConvertPoetErrorStatus(ret, poetRet);
                });
            ThrowSgxError(
                ret,
                "Failed to retrieve PSE manifest hash for enclave");
            this->ThrowPoetError(poetRet);

            // Copy the mr_enclave and basenaeme to the caller's buffers
            memcpy_s(
                outEnclaveMeasurement,
                sizeof(*outEnclaveMeasurement),
                &enclaveQuote->report_body.mr_enclave,
                sizeof(*outEnclaveMeasurement));
            memcpy_s(
                outEnclaveBasename,
                sizeof(*outEnclaveBasename),
                &enclaveQuote->basename,
                sizeof(*outEnclaveBasename));
        } // Enclave::GetEnclaveCharacteristics

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::SetSpid(
            const std::string& inSpid
            )
        {
            ThrowIf<ValueError>(inSpid.length() != 32, "Invalid SPID length");

            HexStringToBinary(this->spid.id, sizeof(this->spid.id), inSpid);
        } // Enclave::SetSpid

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::SetSignatureRevocationList(
            const std::string& inSignatureRevocationList
            )
        {
            // Copy the signature revocation list to our internal cached
            // version and then retrieve the, potentially, new quote size
            // and cache that value.
            this->signatureRevocationList = inSignatureRevocationList;

            const uint8_t* pRevocationList = nullptr;
            uint32_t revocationListSize = this->signatureRevocationList.size();
            if (revocationListSize) {
                pRevocationList =
                    reinterpret_cast<const uint8_t *>(
                        this->signatureRevocationList.c_str());
            }

            uint32_t size;
            ThrowSgxError(sgx_calc_quote_size(pRevocationList, revocationListSize, &size));
            this->quoteSize = size;
        } // Enclave::SetSignatureRevocationList

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::CreateSignupData(
            const std::string& inOriginatorPublicKeyHash,
            sgx_ec256_public_t* outPoetPublicKey,
            buffer_t& outEnclaveQuote,
            sgx_ps_sec_prop_desc_t* outPseManifest,
            buffer_t& outSealedSignupData
            )
        {
            ThrowIfNull(
                outPoetPublicKey,
                "PoET public key pointer is NULL");
            ThrowIfNull(
                outPseManifest,
                "PSE manifest pointer is NULL");

            // We need target info in order to create signup data report
            sgx_target_info_t targetInfo = { 0 };
            sgx_epid_group_id_t gid = { 0 };

            sgx_status_t ret =
                this->CallSgx([&targetInfo, &gid] () {
                    return sgx_init_quote(&targetInfo, &gid);
                });
            ThrowSgxError(
                ret,
                "Failed to initialize quote for CreateSignupData");

            sgx_report_t enclaveReport = { 0 };
            poet_err_t poetRet = POET_SUCCESS;

            // Properly size the sealed signup data buffer for the caller
            // and call into the enclave to create the signup data
            outSealedSignupData.resize(this->sealedSignupDataSize);
            ret =
                this->CallSgx(
                    [this,
                     &poetRet,
                     &targetInfo,
                     inOriginatorPublicKeyHash,
                     outPoetPublicKey,
                     &enclaveReport,
                     &outSealedSignupData,
                     outPseManifest] () {
                    sgx_status_t ret =
                        ecall_CreateSignupData(
                            this->enclaveId,
                            &poetRet,
                            &targetInfo,
                            inOriginatorPublicKeyHash.c_str(),
                            outPoetPublicKey,
                            &enclaveReport,
                            &outSealedSignupData[0],
                            outSealedSignupData.size(),
                            outPseManifest);
                    return ConvertPoetErrorStatus(ret, poetRet);
                });
            ThrowSgxError(
                ret,
                "Failed to generate signup data");
            this->ThrowPoetError(poetRet);

            // Create a linkable quote from the enclave report.

            const uint8_t* pRevocationList = nullptr;
            if (this->signatureRevocationList.size()) {
                pRevocationList =
                    reinterpret_cast<const uint8_t *>(
                        this->signatureRevocationList.c_str());
            }

            // Properly size the enclave quote buffer for the caller and zero it
            // out so we have predicatable contents.
            outEnclaveQuote.resize(this->quoteSize);

            ret =
                this->CallSgx(
                    [this,
                     &enclaveReport,
                     pRevocationList,
                     &outEnclaveQuote] () {
                    return
                        sgx_get_quote(
                            &enclaveReport,
                            SGX_LINKABLE_SIGNATURE,
                            &this->spid,
                            nullptr,
                            pRevocationList,
                            static_cast<uint32_t>(
                                this->signatureRevocationList.size()),
                            nullptr,
                            reinterpret_cast<sgx_quote_t *>(&outEnclaveQuote[0]),
                            static_cast<uint32_t>(outEnclaveQuote.size()));
                });
            ThrowSgxError(
                ret,
                "Failed to create linkable quote for enclave report");
        } // Enclave::GenerateSignupData

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::UnsealSignupData(
            const buffer_t& inSealedSignupData,
            sgx_ec256_public_t* outPoetPublicKey
            )
        {
            ThrowIfNull(
                outPoetPublicKey,
                "PoET public key pointer is NULL");

            // Call down into the enclave to unseal the signup data
            poet_err_t poetRet = POET_SUCCESS;
            sgx_status_t ret =
                this->CallSgx(
                    [this,
                     &poetRet,
                     &inSealedSignupData,
                     outPoetPublicKey] () {
                    sgx_status_t ret =
                        ecall_UnsealSignupData(
                            this->enclaveId,
                            &poetRet,
                            &inSealedSignupData[0],
                            inSealedSignupData.size(),
                            outPoetPublicKey);
                    return ConvertPoetErrorStatus(ret, poetRet);
                });
            ThrowSgxError(
                ret,
                "Failed to unseal signup data");
            this->ThrowPoetError(poetRet);
        } // Enclave::UnsealSignupData

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::ReleaseSignupData(
            const buffer_t& inSealedSignupData
            )
        {
            // Call down into the enclave to release the signup data
            poet_err_t poetRet = POET_SUCCESS;
            sgx_status_t ret =
                this->CallSgx(
                    [this,
                     &poetRet,
                     &inSealedSignupData] () {
                    sgx_status_t ret =
                        ecall_ReleaseSignupData(
                            this->enclaveId,
                            &poetRet,
                            &inSealedSignupData[0],
                            inSealedSignupData.size());
                    return ConvertPoetErrorStatus(ret, poetRet);
                });
            ThrowSgxError(
                ret,
                "Failed to release signup data");
            this->ThrowPoetError(poetRet);
        } // Enclave::ReleaseSignupData

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::VerifySignupInfo(
            const std::string& inOriginatorPublicKeyHash,
            const sgx_ec256_public_t* inPoetPublicKey,
            const sgx_quote_t* inEnclaveQuote,
            size_t inEnclaveQuoteSize,
            const sgx_sha256_hash_t* inPseManifestHash
            )
        {
            ThrowIfNull(inPoetPublicKey, "PoET public key pointer is NULL");
            ThrowIfNull(inEnclaveQuote, "Enclave quote pointer is NULL");

            // We need target info in order to get MRENCLAVE
            sgx_target_info_t targetInfo = { 0 };
            sgx_epid_group_id_t gid = { 0 };

            sgx_status_t ret =
                this->CallSgx([&targetInfo, &gid] () {
                    return sgx_init_quote(&targetInfo, &gid);
                });
            ThrowSgxError(
                ret,
                "Failed to initialize quote for VerifySignupData");

            // Call down into the enclave to verify the signup information
            sgx_report_t testReport = { 0 };
            poet_err_t poetRet = POET_SUCCESS;
            ret =
                this->CallSgx(
                    [this,
                     &poetRet,
                     &targetInfo,
                     inOriginatorPublicKeyHash,
                     inPoetPublicKey,
                     inPseManifestHash,
                     &testReport] () {
                    sgx_status_t ret =
                        ecall_VerifySignupInfo(
                            this->enclaveId,
                            &poetRet,
                            &targetInfo,
                            inOriginatorPublicKeyHash.c_str(),
                            inPoetPublicKey,
                            inPseManifestHash,
                            &testReport);
                    return ConvertPoetErrorStatus(ret, poetRet);
                });
            ThrowSgxError(
                ret,
                "Failed to verify signup data");
            this->ThrowPoetError(poetRet);

            // Verify that the report data is what we epect
            ThrowIf<ValueError>(
                memcmp(
                    &inEnclaveQuote->report_body.report_data,
                    &testReport.body.report_data,
                    sizeof(testReport.body.report_data)) != 0,
                "Report data is invalid");

            // Now compare the enclave measurement (MRENCLAVE).  Currently we
            // are going to compare our own MRENCLAVE to the MRENCAVE value of
            // the other validator.
            ThrowIf<ValueError>(
                memcmp(
                    &inEnclaveQuote->report_body.mr_enclave,
                    &testReport.body.mr_enclave,
                    sizeof(testReport.body.mr_enclave)) != 0,
                "MRENCLAVE in quote does not match expected value");

            // Create a linkable quote from the enclave report so that we can get
            // a basename with which to compare against.

            const uint8_t* pRevocationList = nullptr;
            if (this->signatureRevocationList.size()) {
                pRevocationList =
                    reinterpret_cast<const uint8_t *>(
                        this->signatureRevocationList.c_str());
            }

            // Get an enclave quote so we can verify basename
            buffer_t quote(this->quoteSize);
            sgx_quote_t* pQuote = reinterpret_cast<sgx_quote_t *>(&quote[0]);
            ret =
                this->CallSgx(
                    [this,
                     &testReport,
                     pRevocationList,
                     pQuote] () {
                    return
                        sgx_get_quote(
                            &testReport,
                            SGX_LINKABLE_SIGNATURE,
                            &this->spid,
                            nullptr,
                            pRevocationList,
                            static_cast<uint32_t>(
                                this->signatureRevocationList.size()),
                            nullptr,
                            pQuote,
                            static_cast<uint32_t>(this->quoteSize));
                });
            ThrowSgxError(
                ret,
                "Failed to create linkable quote for enclave report");

            // Now verify that the basename matches what we expect
            ThrowIf<ValueError>(
                memcmp(
                    &inEnclaveQuote->basename,
                    &pQuote->basename,
                    sizeof(pQuote->basename)) != 0,
                "Basename in quote does not match expected value");
        } // Enclave::VerifySignupInfo

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::CreateWaitTimer(
            const buffer_t& inSealedSignupData,
            const std::string& inValidatorAddress,
            const std::string& inPreviousCertificateId,
            double requestTime,
            double localMean,
            char* outSerializedTimer,
            size_t inSerializedTimerLength,
            sgx_ec256_signature_t* outTimerSignature
            )
        {
            ThrowIfNull(
                outSerializedTimer,
                "Serialized wait timer pointer is NULL");
            ThrowIfNull(
                outTimerSignature,
                "Wait timer signature pointer is NULL");

            // Let the enclave create a wait timer for us
            poet_err_t poetRet = POET_SUCCESS;
            sgx_status_t ret =
                this->CallSgx(
                    [this,
                     &poetRet,
                     &inSealedSignupData,
                     inValidatorAddress,
                     inPreviousCertificateId,
                     requestTime,
                     localMean,
                     outSerializedTimer,
                     inSerializedTimerLength,
                     outTimerSignature] () {
                    sgx_status_t ret =
                        ecall_CreateWaitTimer(
                            this->enclaveId,
                            &poetRet,
                            &inSealedSignupData[0],
                            inSealedSignupData.size(),
                            inValidatorAddress.c_str(),
                            inPreviousCertificateId.c_str(),
                            requestTime,
                            localMean,
                            outSerializedTimer,
                            inSerializedTimerLength,
                            outTimerSignature);
                    return ConvertPoetErrorStatus(ret, poetRet);
                });
            ThrowSgxError(ret, "Call to ecall_CreateWaitTimer failed");
            this->ThrowPoetError(poetRet);
        } // Enclave::CreateWaitTimer

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::CreateWaitCertificate(
            const buffer_t& inSealedSignupData,
            const std::string& inSerializedWaitTimer,
            const sgx_ec256_signature_t* inWaitTimerSignature,
            const std::string& inBlockHash,
            char* outSerializedWaitCertificate,
            size_t inSerializedWaitCertificateLength,
            sgx_ec256_signature_t* outWaitCertificateSignature
            )
        {
            ThrowIfNull(
                inWaitTimerSignature,
                "Wait timer signature pointer is NULL");
            ThrowIfNull(
                outSerializedWaitCertificate,
                "Serialized wait certificate pointer is NULL");
            ThrowIfNull(
                outWaitCertificateSignature,
                "Wait certificate signature pointer is NULL");

            poet_err_t poetRet = POET_SUCCESS;
            sgx_status_t ret =
                this->CallSgx(
                    [this,
                     &poetRet,
                     &inSealedSignupData,
                     inSerializedWaitTimer,
                     inWaitTimerSignature,
                     inBlockHash,
                     outSerializedWaitCertificate,
                     inSerializedWaitCertificateLength,
                     outWaitCertificateSignature] () {
                    sgx_status_t ret =
                        ecall_CreateWaitCertificate(
                            this->enclaveId,
                            &poetRet,
                            &inSealedSignupData[0],
                            inSealedSignupData.size(),
                            inSerializedWaitTimer.c_str(),
                            inWaitTimerSignature,
                            inBlockHash.c_str(),
                            outSerializedWaitCertificate,
                            inSerializedWaitCertificateLength,
                            outWaitCertificateSignature);
                    return ConvertPoetErrorStatus(ret, poetRet);
                });
            ThrowSgxError
                (ret,
                "Call to ecall_CreateWaitCertificate failed");
            this->ThrowPoetError(poetRet);
        } // Enclave::CreateWaitCertificate

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::VerifyWaitCertificate(
            const std::string& inSerializedWaitCertificate,
            const sgx_ec256_signature_t* inWaitCertificateSignature,
            const sgx_ec256_public_t* inPoetPublicKey
            )
        {
            ThrowIfNull(
                inWaitCertificateSignature,
                "Wait certificate signature pointer is NULL");
            ThrowIfNull(
                inPoetPublicKey,
                "PoET public key pointer is NULL");

            poet_err_t poetRet = POET_SUCCESS;
            sgx_status_t ret =
                this->CallSgx(
                    [this,
                     &poetRet,
                     inSerializedWaitCertificate,
                     inWaitCertificateSignature,
                     inPoetPublicKey] () {
                    sgx_status_t ret =
                        ecall_VerifyWaitCertificate(
                            this->enclaveId,
                            &poetRet,
                            inSerializedWaitCertificate.c_str(),
                            inWaitCertificateSignature,
                            inPoetPublicKey);
                    return ConvertPoetErrorStatus(ret, poetRet);
                });
            ThrowSgxError(
                ret,
                "Call to ecall_VerifyWaitCertificate failed");
            this->ThrowPoetError(poetRet);
        } // Enclave::VerifyWaitCertificate

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        // XX Private helper methods                                 XX
        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::ThrowPoetError(
            poet_err_t err
            )
        {
            if(err != POET_SUCCESS) {
                std::string tmp(g_enclaveError);
                g_enclaveError.clear();
                throw PoetError(err, tmp.c_str());
            }
        } // Enclave::ThrowPoetError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void Enclave::LoadEnclave()
        {
            if (!this->enclaveId) {
                /* Enclave id, used in communicating with enclave */
                Enclave::QuerySgxStatus();

                sgx_launch_token_t token = { 0 };
                int flags = SGX_DEBUG_FLAG;

                // First attempt to load the enclave executable
                sgx_status_t ret = SGX_SUCCESS;
                ret = this->CallSgx([this, flags, &token] () {
                        int updated = 0;
                        return sgx_create_enclave(
                            this->enclaveFilePath.c_str(),
                            flags,
                            &token,
                            &updated,
                            &this->enclaveId,
                            NULL);
                    },
                    10, // retries
                    250 // retryWaitMs
                    );
                ThrowSgxError(ret, "Unable to create enclave.");

                // Initialize the enclave
                poet_err_t poetError = POET_SUCCESS;
                Log(POET_LOG_INFO, "ecall_Initialize");
                ret = this->CallSgx([this, &poetError] () {
                        sgx_status_t ret =
                            ecall_Initialize(
                                this->enclaveId,
                                &poetError,
                                &this->raContext);
                        return ConvertPoetErrorStatus(ret, poetError);
                    });
                ThrowSgxError(
                    ret,
                    "Enclave call to ecall_Initialize failed");
                this->ThrowPoetError(poetError);

                // We need to figure out a priori the size of the sealed signup
                // data so that caller knows the proper size for the buffer when
                // creating signup data.
                ret =
                    this->CallSgx([this, &poetError] () {
                        sgx_status_t ret =
                            ecall_CalculateSealedSignupDataSize(
                                this->enclaveId,
                                &poetError,
                                &this->sealedSignupDataSize);
                        return
                            ConvertPoetErrorStatus(ret, poetError);
                    });
                ThrowSgxError(
                    ret,
                    "Failed to calculate length of sealed signup data");
                this->ThrowPoetError(poetError);
            }
        } // Enclave::LoadEnclave

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        sgx_status_t Enclave::CallSgx(
            std::function<sgx_status_t (void)> fxn,
            int retries,
            int retryDelayMs
            )
        {
            sgx_status_t ret = SGX_SUCCESS;
            int count = 0;
            bool retry = true;
            do {
                ret = fxn();
                if (SGX_ERROR_ENCLAVE_LOST == ret) {
                    // Enclave lost, potentially due to power state change
                    // reload the enclave and try again
                    this->Unload();
                    this->LoadEnclave();
                } else if (SGX_ERROR_DEVICE_BUSY == ret) {
                    // Device is busy... wait and try again.
                    Sleep(retryDelayMs);
                    count++;
                    retry = count <= retries;
                } else {
                    // Not an error code we need to handle here,
                    // exit the loop and let the calling function handle it.
                    retry = false;
                }
            } while (retry);

            return ret;
        } // Enclave::CallSgx

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

        /* This function is run as the very first step in the attestation
           process to check the device status; query the status of the SGX
           device.  If not enabled before, enable it. If the device is not
           enabled, SGX device not found error is expected when the enclave is
           created.
        */
        void Enclave::QuerySgxStatus()
        {
            sgx_device_status_t sgx_device_status;
            sgx_status_t ret = sgx_enable_device(&sgx_device_status);
            ThrowSgxError(ret);

            switch (sgx_device_status) {
                case SGX_ENABLED:
                    break;
                case SGX_DISABLED_REBOOT_REQUIRED:
                    throw RuntimeError(
                        "SGX device will be enabled after this machine is "
                        "rebooted.\n");
                    break;
                case SGX_DISABLED_LEGACY_OS:
                    throw RuntimeError(
                        "SGX device can't be enabled on an OS that doesn't "
                        "support EFI interface.\n");
                    break;
                case SGX_DISABLED:
                    throw RuntimeError("SGX device not found.\n");
                    break;
                default:
                    throw RuntimeError("Unexpected error.\n");
                    break;
            }
        } // Enclave::QuerySgxStatus

    } // namespace poet
} // namespace sawtooth

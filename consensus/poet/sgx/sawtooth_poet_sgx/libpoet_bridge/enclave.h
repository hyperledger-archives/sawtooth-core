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

#pragma once 
#include <functional>
#include <memory>
#include <string>
#include <vector>

#include "sgx_urts.h"
#include "sgx_key_exchange.h"

#include "poet.h"
#include "sealed_data.h"

namespace sawtooth {
    namespace poet {

        class Enclave {
        public:
            typedef std::vector<uint8_t> buffer_t;

            Enclave();
            virtual ~Enclave();

            void Load(
                const std::string& inEnclaveFilePath
                );
            void Unload();

            size_t GetQuoteSize() const
            {
                return this->quoteSize;
            } // GetQuoteSize
            size_t GetSealedSignupDataSize() const
            {
                return this->sealedSignupDataSize;
            } // GetSealedSignupDataSize

            void GetEpidGroup(
                sgx_epid_group_id_t outEpidGroup
                );
            void GetEnclaveCharacteristics(
                sgx_measurement_t* outEnclaveMeasurement,
                sgx_basename_t* outEnclaveBasename,
                sgx_sha256_hash_t* outEnclavePseManifestHash
                );
            void SetSpid(
                const std::string& inSpid
                );
            void SetDataDirectory(
                const std::string& inDataDirectory
                )
            {
                dataDirectory = inDataDirectory;
            } // SetDataDirectory

            void SetSignatureRevocationList(
                const std::string& inSignatureRevocationList
                );

            void CreateSignupData(
                const std::string& inOriginatorPublicKeyHash,
                sgx_ec256_public_t* outPoetPublicKey,
                buffer_t& outEnclaveQuote,
                sgx_ps_sec_prop_desc_t* outPseManifest,
                buffer_t& outSealedSignupData
                );
            void UnsealSignupData(
                const buffer_t& inSealedSignupData,
                sgx_ec256_public_t* outPoetPublicKey
                );
            void ReleaseSignupData(
                const buffer_t& inSealedSignupData
                );
            void VerifySignupInfo(
                const std::string& inOriginatorPublicKeyHash,
                const sgx_ec256_public_t* inPoetPublicKey,
                const sgx_quote_t* inEnclaveQuote,
                size_t inEnclaveQuoteSize,
                const sgx_sha256_hash_t* inPseManifestHash
                );

            void CreateWaitTimer(
                const buffer_t& inSealedSignupData,
                const std::string& inValidatorAddress,
                const std::string& inPreviousCertificateId,
                double requestTime,
                double localMean,
                char* outSerializedTimer,
                size_t inSerializedTimerLength,
                sgx_ec256_signature_t* outTimerSignature
                );

            void CreateWaitCertificate(
                const buffer_t& inSealedSignupData,
                const std::string& inSerializedWaitTimer,
                const sgx_ec256_signature_t* inWaitTimerSignature,
                const std::string& inBlockHash,
                char* outSerializedWaitCertificate,
                size_t inSerializedWaitCertificateLength,
                sgx_ec256_signature_t* outWaitCertificateSignature
                );
            void VerifyWaitCertificate(
                const std::string& inSerializedWaitCertificate,
                const sgx_ec256_signature_t* inWaitCertificateSignature,
                const sgx_ec256_public_t* inPoetPublicKey
                );

        private:
            void ThrowPoetError(
                poet_err_t err
                );
            void LoadEnclave();
            sgx_status_t CallSgx(
                std::function<sgx_status_t (void)> sgxCall, 
                int retries = 5, 
                int retryDelayMs = 100
                );

            static void QuerySgxStatus();
        private:
            std::string enclaveFilePath;
            sgx_enclave_id_t enclaveId;
            sgx_ra_context_t raContext;

            size_t quoteSize;
            size_t sealedSignupDataSize;

            std::string signatureRevocationList;
            sgx_spid_t spid;
            std::string dataDirectory;
        }; // class Enclave

    } // namespace poet
} // namespace sawtooth

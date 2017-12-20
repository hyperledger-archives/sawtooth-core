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

#include <json-c/json.h>

#include "poet_enclave.h"
#include "common.h"
#include "poet.h"

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WaitCertificate::WaitCertificate(
    const std::string& sealedSignupData,
    const WaitTimer* waitTimer,
    const std::string& blockHash
    )
{
    PyLog(POET_LOG_INFO, "Create SGX Wait Certificate");

    StringBuffer serializedBuffer(Poet_GetWaitCertificateSize());
    StringBuffer signatureBuffer(Poet_GetSignatureSize());

     poet_err_t ret =
        Poet_CreateWaitCertificate(
            sealedSignupData.c_str(),
            waitTimer->serialized.c_str(),
            waitTimer->signature.c_str(),
            blockHash.c_str(),
            serializedBuffer.data(),
            serializedBuffer.length,
            signatureBuffer.data(),
            signatureBuffer.length);
    ThrowPoetError(ret);

    this->serialized = serializedBuffer.str();
    this->signature = signatureBuffer.str();
    this->deserialize(this->serialized);
} // WaitCertificate::WaitCertificate

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WaitCertificate::WaitCertificate(
    const std::string& serializedCertificate,
    const std::string& signature
    ) :
    serialized(serializedCertificate),
    signature(signature)
{
    this->deserialize(this->serialized);
} // WaitCertificate::WaitCertificate

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WaitCertificate* WaitCertificate::_CreateWaitCertificate(
    const std::string& sealedSignupData,
    const WaitTimer* waitTimer,
    const std::string& blockHash
    )
{
    return new WaitCertificate(sealedSignupData, waitTimer, blockHash);
} // WaitCertificate::_CreateWaitCertificate

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WaitCertificate* WaitCertificate::_WaitCertificateFromSerialized(
    const std::string& serializedCertificate,
    const std::string& signature
    )
{
    return new WaitCertificate(serializedCertificate, signature);
} // WaitCertificate::_WaitCertificateFromSerialized

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
std::string WaitCertificate::identifier() const
{
    if (this->signature.empty()) {
        return NULL_IDENTIFIER;
    }

    return CreateIdentifier(this->signature);
} // WaitCertificate::identifier

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
std::string WaitCertificate::serialize() const
{
    return this->serialized;
} // WaitCertificate::serialize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void WaitCertificate::deserialize(
    const std::string&  serializedCertificate
    )
{
    json_object* jsonObject = json_tokener_parse(serializedCertificate.c_str());
    if (!jsonObject) {
        throw ValueError("Failed to parse serialized wait certificate");
    }

    json_object* jsonValue = NULL;

    // Use alphabetical order for the keys
    if (json_object_object_get_ex(jsonObject, "BlockHash", &jsonValue)) {
        this->block_hash = json_object_get_string(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract BlockHash from serialized wait certificate");
    }

    if (json_object_object_get_ex(jsonObject, "Duration", &jsonValue)) {
        this->duration = json_object_get_double(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract Duration from serialized wait certificate");
    }

    if (json_object_object_get_ex(jsonObject, "LocalMean", &jsonValue)) {
        this->local_mean = json_object_get_double(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract LocalMean from serialized wait certificate");
    }

    if (json_object_object_get_ex(jsonObject, "Nonce", &jsonValue)) {
        this->nonce = json_object_get_string(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract Nonce from serialized wait certificate");
    }

    if (json_object_object_get_ex(jsonObject, "PreviousCertID", &jsonValue)) {
        this->previous_certificate_id = json_object_get_string(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract PreviousCertID from serialized wait "
                "certificate");
    }

    if (json_object_object_get_ex(jsonObject, "RequestTime", &jsonValue)) {
        this->request_time = json_object_get_double(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract RequestTime from serialized wait "
                "certificate");
    }

    if (json_object_object_get_ex(jsonObject, "ValidatorAddress", &jsonValue)) {
        this->validator_address = json_object_get_string(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract ValidatorAddress from serialized wait "
                "certificate");
    }
} // WaitCertificate::deserialize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WaitCertificate* create_wait_certificate(
    const std::string& sealed_signup_data,
    const WaitTimer* wait_timer,
    const std::string& block_hash
    )
{
    if (!wait_timer) {
        throw ValueError("wait_timer is NULL");
    }

    return
        WaitCertificate::_CreateWaitCertificate(
            sealed_signup_data,
            wait_timer,
            block_hash);
} // create_wait_certificate

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WaitCertificate* deserialize_wait_certificate(
    const std::string& serialized_certificate,
    const std::string& signature
    )
{
    return
        WaitCertificate::_WaitCertificateFromSerialized(
            serialized_certificate,
            signature);
} // deserialize_wait_certificate

bool _verify_wait_certificate(
    const std::string& serializedWaitCertificate,
    const std::string& waitCertificateSignature,
    const std::string& poetPublicKey
    )
{
    PyLog(POET_LOG_INFO, "Verify SGX Wait Certificate");

    poet_err_t ret =
        Poet_VerifyWaitCertificate(
            serializedWaitCertificate.c_str(),
            waitCertificateSignature.c_str(),
            poetPublicKey.c_str() );
    ThrowPoetError(ret);

    if(ret == POET_SUCCESS) return true;
    return false;
}
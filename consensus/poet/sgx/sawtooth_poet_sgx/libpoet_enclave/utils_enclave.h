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

#include <sgx_tae_service.h>
#include <functional>
#include <stdint.h>
#include "parson.h"
#include "error.h"

namespace sp = sawtooth::poet;

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
class PseSession
{
public:
    PseSession()
    {
        sp::ThrowSgxError(
            sgx_create_pse_session(),
            "Failed to create PSE session.");
    } // PseSession

    virtual ~PseSession()
    {
        sgx_close_pse_session();
    } // ~PseSession
}; // class PseSession

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
class JsonValue
{
public: 
    JsonValue(JSON_Value* value = nullptr)
    {
        this->value = value;
    } // JsonValue

    virtual ~JsonValue()
    {
        if (this->value) {
            json_value_free(this->value);
        }
    } // ~JsonValue

    operator JSON_Value* ()
    {
        return value;
    } // operator JSON_Value*

    operator const JSON_Value* () const
    {
        return value;
    } // operator JSON_Value*

    JSON_Value* value;
}; // JsonValue

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
/* Holder for binary representation of WaitTimer */
typedef struct _WaitTimer
{
    double Duration;
    double LocalMean;
    std::string PreviousCertificateId; // no null terminator
    uint32_t SequenceId; // the sequenceId of the generated WaitTimer - used to prevent validators from submitting old expired wait   
    double RequestTime; // system request time - from the validator
    double SgxRequestTime; // The time from the sgx trusted time source
    sgx_time_source_nonce_t TimeSourceNonce; // 
    std::string ValidatorAddress;  
} WaitTimer;

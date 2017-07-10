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
WaitTimer::WaitTimer(
    const std::string& validatorAddress,
    const std::string& previousCertificateId,
    double localMean,
    double minimumWaitTime
    )
{
    StringBuffer serializedBuffer(Poet_GetWaitTimerSize());
    std::vector<char> signatureBuffer(Poet_GetSignatureSize());

    poet_err_t ret =
        Poet_CreateWaitTimer(
            validatorAddress.c_str(),
            previousCertificateId.c_str(),
            CurrentTime(),
            localMean,
            minimumWaitTime,
            serializedBuffer.data(),
            serializedBuffer.length,
            &signatureBuffer[0],
            signatureBuffer.size());
    ThrowPoetError(ret);

    this->serialized = serializedBuffer.str();
    this->signature = std::string(&signatureBuffer[0]);
    this->deserialize(serialized);
} // WaitTimer::WaitTimer

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WaitTimer::WaitTimer(
    const std::string& serializedTimer,
    const std::string& signature
    ) :
    serialized(serializedTimer),
    signature(signature)
{
    this->deserialize(serializedTimer);
} // WaitTimer::WaitTimer

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WaitTimer* WaitTimer::_CreateWaitTimer(
    const std::string& validatorAddress,
    const std::string& previousCertificateId,
    double localMean,
    double minimumWaitTime
    )
{
    return 
        new WaitTimer(
            validatorAddress,
            previousCertificateId,
            localMean,
            minimumWaitTime);
} // WaitTimer::_CreateWaitTimer

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WaitTimer* WaitTimer::_WaitTimerFromSerialized(
    const std::string& serializedTimer,
    const std::string& signature
    )
{
    return new WaitTimer(serializedTimer, signature);
} // WaitTimer::_WaitTimerFromSerialized

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
bool WaitTimer::has_expired() const
{
    double currentTime = CurrentTime();
    double expireTime = this->request_time + this->duration;
    return (expireTime < currentTime) ? true : false;
} // WaitTimer::has_expired

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void WaitTimer::deserialize(
    const std::string& serializedTimer
    )
{
    json_object* jsonObject = json_tokener_parse(serializedTimer.c_str());
    if (!jsonObject) {
        throw ValueError("Failed to parse serialized wait timer");
    }

    json_object* jsonValue = NULL;

    // Use alphabetical order for the keys
    if (json_object_object_get_ex(jsonObject, "Duration", &jsonValue)) {
        this->duration = json_object_get_double(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract Duration from serialized wait timer");
    }

    if (json_object_object_get_ex(jsonObject, "LocalMean", &jsonValue)) {
        this->local_mean = json_object_get_double(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract LocalMean from serialized wait timer");
    }

    if (json_object_object_get_ex(jsonObject, "PreviousCertID", &jsonValue)) {
        this->previous_certificate_id = json_object_get_string(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract PreviousCertID from serialized wait timer");
    }

    if (json_object_object_get_ex(jsonObject, "RequestTime", &jsonValue)) {
        this->request_time = json_object_get_double(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract RequestTime from serialized wait timer");
    }

    if (json_object_object_get_ex(jsonObject, "ValidatorAddress", &jsonValue)) {
        this->validator_address = json_object_get_string(jsonValue);
    } else {
        throw
            ValueError(
                "Failed to extract ValidatorAddress from serialized wait "
                "timer");
    }
} // WaitTimer::deserialize

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WaitTimer* _create_wait_timer(
    const std::string& validator_address,
    const std::string& previous_certificate_id,
    double local_mean,
    double minimum_wait_time
    )
{
    return
        WaitTimer::_CreateWaitTimer(
            validator_address,
            previous_certificate_id,
            local_mean,
            minimum_wait_time);
} // create_wait_timer

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
WaitTimer* deserialize_wait_timer(
    const std::string& serialized_timer,
    const std::string& signature)
{
    return WaitTimer::_WaitTimerFromSerialized(serialized_timer, signature);
} // deserialize_wait_timer

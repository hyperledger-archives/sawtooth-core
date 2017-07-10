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
SignupInfo::SignupInfo(
    const std::string& serializedSignupInfo
    ) :
    serialized(serializedSignupInfo)
{
    json_object* jsonObject =
        json_tokener_parse(const_cast<char *>(serialized.c_str()));
    if (!jsonObject) {
        throw ValueError("Failed to parse serialized signup info");
    }

    json_object* jsonValue = NULL;

    if (json_object_object_get_ex(jsonObject, "poet_public_key", &jsonValue)) {
        this->poet_public_key = json_object_get_string(jsonValue);
    } else {
        throw ValueError(
            "Failed to extract poet_public_key from serialized signup info");
    }

    if (json_object_object_get_ex(jsonObject, "proof_data", &jsonValue)) {
        this->proof_data = json_object_get_string(jsonValue);
    } else {
        throw ValueError(
            "Failed to extract proof_data from serialized signup info");
    }

    if (json_object_object_get_ex(
            jsonObject,
            "anti_sybil_id",
            &jsonValue)) {
        this->anti_sybil_id = json_object_get_string(jsonValue);
    } else {
        throw ValueError(
            "Failed to extract anti_sybil_id from serialized signup info");
    }
} // SignupInfo::SignupInfo

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
SignupInfo* SignupInfo::_SignupInfoFromSerialized(
    const std::string& serializedSignupInfo
    )
{
    return new SignupInfo(serializedSignupInfo);
} // SignupInfo::SignupInfoFromSerialized

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
SignupInfo* deserialize_signup_info(
    const std::string&  serialized_signup_info
    )
{
    return SignupInfo::_SignupInfoFromSerialized(serialized_signup_info);
} // deserialize_signup_info

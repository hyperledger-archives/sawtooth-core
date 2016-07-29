// Copyright 2016 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ------------------------------------------------------------------------------

#ifdef _WIN32
    #include <windows.h>
    #include <random>
#else
    #include <sys/time.h>
#endif
#include <time.h>
#include <stdlib.h>
#include <string>
#include <json-c/json.h>

#include "poet_enclave.h"
#include "common.h"

using namespace std;

WaitCertificate::WaitCertificate(string encoded, string signature)
{
    this->signature = signature;
    this->deserialize(encoded);
}

WaitCertificate::WaitCertificate(WaitTimer *timer, string block_hash)
{
    this->request_time = timer->request_time;
    this->duration = timer->duration;
    this->local_mean = timer->local_mean;
    this->previous_certificate_id = timer->previous_certificate_id;
    this->validator_address = timer->validator_address;
    this->block_hash = block_hash;
    this->signature = "";
}

string WaitCertificate::identifier(void)
{
    if (this->signature == "")
        return NULL_IDENTIFIER;

    return CreateIdentifier(this->signature);
}

bool WaitCertificate::deserialize(string serialized)
{
    json_object *jobj = json_tokener_parse((char *)serialized.data());
    if (jobj == NULL)
        return false;

    struct json_object *obj = NULL;

    // Use alphabetical order for the keys
    if (json_object_object_get_ex(jobj, "BlockHash", &obj))
        block_hash = json_object_get_string(obj);

    if (json_object_object_get_ex(jobj, "Duration", &obj))
        duration = json_object_get_double(obj);

    if (json_object_object_get_ex(jobj, "LocalMean", &obj))
        local_mean = json_object_get_double(obj);

    if (json_object_object_get_ex(jobj, "PreviousCertID", &obj))
        previous_certificate_id = json_object_get_string(obj);

    if (json_object_object_get_ex(jobj, "RequestTime", &obj))
        request_time = json_object_get_double(obj);

    if (json_object_object_get_ex(jobj, "ValidatorAddress", &obj))
        validator_address = json_object_get_string(obj);

    return true;
}

string WaitCertificate::serialize()
{
    json_object *jobj = json_object_new_object();

    // Use alphabetical order for the keys
    json_object_object_add(jobj, "BlockHash", json_object_new_string(block_hash.c_str()));
    json_object_object_add(jobj, "Duration", json_object_new_double(duration));
    json_object_object_add(jobj, "LocalMean", json_object_new_double(local_mean));
    json_object_object_add(jobj, "PreviousCertID", json_object_new_string((char *)previous_certificate_id.c_str()));
    json_object_object_add(jobj, "RequestTime", json_object_new_double(request_time));
    json_object_object_add(jobj, "ValidatorAddress", json_object_new_string(validator_address.c_str()));

    string serialized = (char *)json_object_to_json_string(jobj);
    return serialized;
}

WaitCertificate* create_wait_certificate(WaitTimer *timer, string block_hash)
{
    // the timer must have been created by the enclave
    string serialized_timer = timer->serialize();
    if (! verify_signature(WaitTimerPublicKey, serialized_timer,
                            timer->signature)) {
        return NULL;
    }

    if (timer->sequence_id != WaitTimer::get_current_sequence_id())
    {
        return NULL;
    }


    // and the timer must have expired or the previous cert must be the nullidentifier
    if (timer->previous_certificate_id != NULL_IDENTIFIER
        && (! timer->is_expired()))
    {
        return NULL;
    }



    WaitCertificate *cert = new WaitCertificate(timer, block_hash);
    cert->signature = SignMessage(GlobalPrivateKey, cert->serialize());

    return cert;
}

WaitCertificate* deserialize_wait_certificate(
    string serialized_cert,
    string signature)
{
    if (! verify_signature(GlobalPublicKey, serialized_cert,
                            signature)) {
        throw ValueError("Signature failed to verify.");
    }

    WaitCertificate *cert = new WaitCertificate(serialized_cert, signature);

    return cert;
}

bool verify_wait_certificate(WaitCertificate *cert)
{
    if(cert == NULL) {
        throw ValueError("Invalid Certificate.");
    }

    string serialized = cert->serialize();
    return verify_signature(GlobalPublicKey, serialized, cert->signature);
}

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
    this->minimum_wait_time = 1.0;
    this->signature = signature;
    this->deserialize(encoded);
}

WaitCertificate::WaitCertificate(WaitTimer *timer)
{
    this->minimum_wait_time = timer->minimum_wait_time;
    this->request_time = timer->request_time;
    this->duration = timer->duration;
    this->local_mean = timer->local_mean;
    this->previous_certificate_id = timer->previous_certificate_id;
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
    if (json_object_object_get_ex(jobj, "Duration", &obj))
        duration = json_object_get_double(obj);

    if (json_object_object_get_ex(jobj, "LocalMean", &obj))
        local_mean = json_object_get_double(obj);

    if (json_object_object_get_ex(jobj, "MinimumWaitTime", &obj))
        minimum_wait_time = json_object_get_double(obj);

    if (json_object_object_get_ex(jobj, "PreviousCertID", &obj))
        previous_certificate_id = json_object_get_string(obj);

    if (json_object_object_get_ex(jobj, "RequestTime", &obj))
        request_time = json_object_get_double(obj);

    return true;
}

string WaitCertificate::serialize()
{
    json_object *jobj = json_object_new_object();

    // Use alphabetical order for the keys
    json_object_object_add(jobj, "Duration", json_object_new_double(duration));
    json_object_object_add(jobj, "LocalMean", json_object_new_double(local_mean));
    json_object_object_add(jobj, "MinimumWaitTime", json_object_new_double(minimum_wait_time));
    json_object_object_add(jobj, "PreviousCertID", json_object_new_string((char *)previous_certificate_id.data()));
    json_object_object_add(jobj, "RequestTime", json_object_new_double(request_time));

    string serialized = (char *)json_object_to_json_string(jobj);
    return serialized;
}

WaitCertificate* create_wait_certificate(WaitTimer *timer)
{
    // the timer must have been created by the enclave
    string serialized_timer = timer->serialize();
    if (! verify_signature(WaitTimerPublicKey, serialized_timer,
                            timer->signature)) {
        return NULL;
    }

    // and the timer must have expired or the previous cert must be the nullidentifier
    if (timer->previous_certificate_id != NULL_IDENTIFIER && (! timer->is_expired()))
        return NULL;

    WaitCertificate *cert = new WaitCertificate(timer);
    cert->signature = SignMessage(GlobalPrivateKey, cert->serialize());

    return cert;
}

WaitCertificate* deserialize_wait_certificate(string serialized_cert,
                    string signature)
{
    WaitCertificate *cert = new WaitCertificate(serialized_cert, signature);
    return cert;
}

bool verify_wait_certificate(WaitCertificate *cert)
{
    string serialized = cert->serialize();
    return verify_signature(GlobalPublicKey, serialized, cert->signature);
}

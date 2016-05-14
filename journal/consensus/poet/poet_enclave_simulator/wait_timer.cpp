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
#ifdef __APPLE__
    #include <random>
#endif
#include <algorithm>
#include <memory>
#include <time.h>
#include <stdlib.h>
#include <string>
#include <json-c/json.h>
#include <iostream>

#include "poet_enclave.h"
#include "common.h"

using namespace std;

static double ComputeDuration(double mean)
{
#ifdef _WIN32
    SYSTEMTIME seed;GetLocalTime(&seed);
    std::tr1::mt19937 generator((int) seed.wMilliseconds);
    std::tr1::exponential_distribution<double> distribution(1.0 / mean);
#else
    struct timeval seed;
    gettimeofday(&seed, NULL);

    std::default_random_engine generator(seed.tv_usec);
    std::exponential_distribution<double> distribution(1.0 / mean);
#endif

    double wait = distribution(generator);

    return (MINIMUM_WAIT_TIME + wait);
}

WaitTimer::WaitTimer(string encoded, string signature)
{
    this->signature = signature;
    this->deserialize(encoded);
}

WaitTimer::WaitTimer(string previous_certificate_id, double local_mean)
{
    if(local_mean <= 0) {
        throw ValueError("Invalid local mean");
    }

    if(previous_certificate_id.length() != IDENTIFIER_LENGTH) {
        throw ValueError("Invalid previous_certificate_id");
    }

    this->local_mean = local_mean;

    this->request_time = CurrentTime();
    this->duration = ComputeDuration(local_mean);

    this->previous_certificate_id = previous_certificate_id;
}

bool WaitTimer::is_expired(void)
{
    return (request_time + duration) < CurrentTime() ? true : false;
}

bool WaitTimer::deserialize(string serialized)
{
    json_object *jobj = json_tokener_parse((char *)serialized.data());
    if (jobj == NULL)
    {
        return false;
    }

    struct json_object *obj = NULL;

    // Use alphabetical order for the keys
    if (json_object_object_get_ex(jobj, "Duration", &obj))
        duration = json_object_get_double(obj);

    if (json_object_object_get_ex(jobj, "LocalMean", &obj))
        local_mean = json_object_get_double(obj);

    if (json_object_object_get_ex(jobj, "PreviousCertID", &obj))
        previous_certificate_id = json_object_get_string(obj);

    if (json_object_object_get_ex(jobj, "RequestTime", &obj))
        request_time = json_object_get_double(obj);

    return true;
}

string WaitTimer::serialize()
{
    json_object *jobj = json_object_new_object();

    // Use alphabetical order for the keys
    json_object_object_add(jobj, "Duration", json_object_new_double(duration));
    json_object_object_add(jobj, "LocalMean", json_object_new_double(local_mean));
    json_object_object_add(jobj, "PreviousCertID", json_object_new_string((char *)previous_certificate_id.data()));
    json_object_object_add(jobj, "RequestTime", json_object_new_double(request_time));

    string serialized = (char *)json_object_to_json_string(jobj);

    return serialized;
}


WaitTimer* create_wait_timer(string prev_cert_id,
                                double local_mean)
{
    WaitTimer *timer = new WaitTimer(prev_cert_id, local_mean);
    timer->signature = SignMessage(WaitTimerPrivateKey, timer->serialize());
    return(timer);
}

WaitTimer* deserialize_wait_timer(string serialized_timer,
                                        string signature)
{
    if(!verify_signature(WaitTimerPublicKey, serialized_timer, signature))
    {
        throw ValueError("Signature failed to verify.");
    }

    WaitTimer* timer = new WaitTimer(serialized_timer, signature);

    return timer;
}

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
// -----------------------------------------------------------------------------

/*
*
* Emulates secure enclave for POET implementation.
*/

#include <string>

// This is the identifier for the genesis block
const std::string NULL_IDENTIFIER = "0000000000000000";
const double MINIMUM_WAIT_TIME = 1.0;

class WaitTimer
{
 public:
    WaitTimer(std::string prev_cert_id, double local_mean);
    WaitTimer(std::string serialized_timer, std::string signature = "");

    bool is_expired(void);

    std::string serialize(void);
    bool deserialize(std::string encoded);

    double local_mean;

    double request_time;
    double duration;

    std::string previous_certificate_id;

    std::string signature;
};

WaitTimer* create_wait_timer(std::string prev_cert_id,
                            double local_mean);
WaitTimer* deserialize_wait_timer(std::string serialized_timer,
                                        std::string signature = "");

class WaitCertificate
{
 public:
    WaitCertificate(WaitTimer *timer);
    WaitCertificate(std::string serialized_cert, std::string signature = "");

    std::string identifier(void);

    std::string serialize(void);
    bool deserialize(std::string encoded);

    double local_mean;

    double request_time;
    double duration;

   std:: string previous_certificate_id;

    std::string signature;
};

WaitCertificate* create_wait_certificate(WaitTimer *timer);
WaitCertificate* deserialize_wait_certificate(std::string serialized_cert,
                                        std::string signature = "");
bool verify_wait_certificate(WaitCertificate *cert);

std::string test_sign_message(std::string message);
bool test_verify_message(std::string message, std::string signature);

void InitializePoetEnclaveModule(void);

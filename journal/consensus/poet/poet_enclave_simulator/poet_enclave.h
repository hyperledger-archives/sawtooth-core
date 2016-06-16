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
const int IDENTIFIER_LENGTH = 16;
const double MINIMUM_WAIT_TIME = 1.0;

class WaitTimer
{
 protected:
    friend WaitTimer* create_wait_timer(
        std::string validator_address,
        std::string prev_cert_id,
        double local_mean);
    friend WaitTimer* deserialize_wait_timer(
        std::string serialized_timer,
        std::string signature);
    WaitTimer(
        std::string validator_address,
        std::string prev_cert_id,
        double local_mean);
    WaitTimer(std::string serialized_timer, std::string signature);
public:
    bool is_expired(void);

    std::string serialize(void);
    bool deserialize(std::string encoded);

public:
    double duration;
    double local_mean;
    std::string previous_certificate_id;
    double request_time;
    std::string validator_address;

    std::string signature;
};

WaitTimer* create_wait_timer(std::string validator_address,
                             std::string prev_cert_id,
                             double local_mean);
WaitTimer* deserialize_wait_timer(std::string serialized_timer,
                                  std::string signature);

class WaitCertificate
{
protected:
    friend WaitCertificate* create_wait_certificate(
        WaitTimer *timer,
        std::string block_hash);
    friend  WaitCertificate* deserialize_wait_certificate(
        std::string serialized_cert,
        std::string signature);
    WaitCertificate(
        WaitTimer *timer,
        std::string block_hash);
    WaitCertificate(
        std::string serialized,
        std::string signature);
public:
    std::string identifier(void);

    std::string serialize(void);
    bool deserialize(std::string encoded);

public:
    double local_mean;

    std:: string block_hash;
    double duration;
    std:: string previous_certificate_id;
    double request_time;
    std:: string validator_address;

    std::string signature;
};

WaitCertificate* create_wait_certificate(
    WaitTimer *timer,
    std::string block_hash);
WaitCertificate* deserialize_wait_certificate(
    std::string serialized,
    std::string signature);
bool verify_wait_certificate(WaitCertificate *cert);

void InitializePoetEnclaveModule(void);

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
const std::string NullIdentifier = "0000000000000000";

class WaitTimer
{
 public:
    WaitTimer(std::string pcertid, double localmean);
    WaitTimer(std::string serializedtimer, std::string signature = "");

    bool is_expired(void);

    std::string serialize(void);
    bool Deserialize(std::string encoded);

    double MinimumWaitTime;
    double LocalMean;

    double RequestTime;
    double Duration;

    std::string PreviousCertID;

    std::string Signature;
};

WaitTimer *create_wait_timer(std::string prevcertid, double localmean);
WaitTimer *DeserializeWaitTimer(std::string serializedtimer, std::string signature = "");

class WaitCertificate
{
 public:
    WaitCertificate(WaitTimer *timer);
    WaitCertificate(std::string serializedCert, std::string signature = "");

    std::string Identifier(void);

    std::string serialize(void);
    bool Deserialize(std::string encoded);

    double MinimumWaitTime;
    double LocalMean;

    double RequestTime;
    double Duration;

   std:: string PreviousCertID;

    std::string Signature;
};

WaitCertificate *create_wait_certificate(WaitTimer *timer);
WaitCertificate *deserialize_wait_certificate(std::string serializedcert, std::string signature = "");
bool VerifyWaitCertificate(WaitCertificate *cert);

std::string TestSignMessage(std::string message);
bool TestVerifySignature(std::string message, std::string signature);

void InitializePoetEnclaveModule(void);

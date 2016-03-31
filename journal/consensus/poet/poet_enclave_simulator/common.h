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


#include <stdlib.h>                                                                  
#include <string>

#include <cryptopp/cryptlib.h>
#include <cryptopp/eccrypto.h>
#include <cryptopp/asn.h>

#define ENCODESIGNATURE 1

using namespace std;

extern CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PrivateKey GlobalPrivateKey;
extern CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PublicKey GlobalPublicKey;

extern CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PrivateKey WaitTimerPrivateKey;
extern CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PublicKey WaitTimerPublicKey;

void GenerateGlobalKey(void);
void GenerateWaitTimerKey(void);

string SignMessage(CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PrivateKey privkey, string message);
bool verify_signature(CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PublicKey pubkey, string message, string signature);

double CurrentTime(void);

string CreateIdentifier(string signature);
string B32Encode(string message);
string B32Decode(string encoded);


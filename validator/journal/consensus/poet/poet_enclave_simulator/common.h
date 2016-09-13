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
#include <stdexcept>

#include <cryptopp/cryptlib.h>
#include <cryptopp/eccrypto.h>
#include <cryptopp/asn.h>

#define ENCODESIGNATURE 1



class MemoryError : public std::runtime_error {
public:
    MemoryError(std::string msg) : runtime_error(msg)
    {}
};
class IOError : public std::runtime_error {
public:
    IOError(std::string msg) : runtime_error(msg)
    {}
};
class RuntimeError : public std::runtime_error {
public:
    RuntimeError(std::string msg) : runtime_error(msg)
    {}
};
class IndexError : public std::runtime_error {
public:
    IndexError(std::string msg) : runtime_error(msg)
    {}
};
class TypeError : public std::runtime_error {
public:
    TypeError(std::string msg) : runtime_error(msg)
    {}
};
class DivisionByZero : public std::runtime_error {
public:
    DivisionByZero(std::string msg) : runtime_error(msg)
    {}
};
class OverflowError : public std::runtime_error {
public:
    OverflowError(std::string msg) : runtime_error(msg)
    {}
};
class SyntaxError : public std::runtime_error {
public:
    SyntaxError(std::string msg) : runtime_error(msg)
    {}
};
class ValueError : public std::runtime_error {
public:
    ValueError(std::string msg) : runtime_error(msg)
    {}
};
class SystemError : public std::runtime_error {
public:
    SystemError(std::string msg) : runtime_error(msg)
    {}
};
class UnknownError : public std::runtime_error {
public:
    UnknownError(std::string msg) : runtime_error(msg)
    {}
};


extern CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PrivateKey GlobalPrivateKey;
extern CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PublicKey GlobalPublicKey;

extern CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PrivateKey WaitTimerPrivateKey;
extern CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PublicKey WaitTimerPublicKey;

void GenerateGlobalKey(void);
void GenerateWaitTimerKey(void);

std::string SignMessage(CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PrivateKey privkey, std::string message);
bool verify_signature(CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PublicKey pubkey, std::string message, std::string signature);

double CurrentTime(void);

std::string CreateIdentifier(std::string signature);
std::string B32Encode(std::string message);
std::string B32Decode(std::string encoded);


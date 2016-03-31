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


/*
*
* Emulates secure enclave for POET implementation.
*/

#ifdef _WIN32
    #include <Windows.h>
#else
    #include <sys/time.h>
#endif
#include <time.h>                                                                    
#include <stdlib.h>                                                                  
#include <stdio.h>
#include <string>
#include <random>

#include <cryptopp/cryptlib.h>
#include <cryptopp/eccrypto.h>
#include <cryptopp/asn.h>
#include <cryptopp/oids.h>
#include <cryptopp/base32.h>
#include <cryptopp/integer.h>
#include <cryptopp/osrng.h>
#include <cryptopp/files.h>
#include <iostream>

#include "poet_enclave.h"
#include "common.h"

using namespace std;


const string PassPhrase("4 score year ago our founding fathers got really crazy and declared fridays as beer days");
CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PrivateKey GlobalPrivateKey;
CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PublicKey GlobalPublicKey;

CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PrivateKey WaitTimerPrivateKey;
CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PublicKey WaitTimerPublicKey;

CryptoPP::AutoSeededRandomPool prng;

#if KEYDEBUG
static void PrintPrivateKey( const CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PrivateKey& key )
{   
    std::cout << std::endl;
    std::cout << "Private Exponent:" << std::endl;
    std::cout << " " << key.GetPrivateExponent() << std::endl; 
}

static void SavePrivateKey( const string& filename, const CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PrivateKey& key )
{
    key.DEREncodePrivateKey(CryptoPP::FileSink(filename.c_str(),true).Ref());
}

static void PrintPublicKey( const CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PublicKey& key )
{   
    std::cout << std::endl;
    std::cout << "Public Element:" << std::endl;
    std::cout << " X: " << key.GetPublicElement().x << std::endl; 
    std::cout << " Y: " << key.GetPublicElement().y << std::endl;
}

static void SavePublicKey( const string& filename, const CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PublicKey& key )
{   
    key.DEREncodePublicKey(CryptoPP::FileSink(filename.c_str(),true).Ref());
}
#endif

void GenerateGlobalKey(void)
{
    unsigned char digest[CryptoPP::SHA256::DIGESTSIZE];

    CryptoPP::SHA256().CalculateDigest(digest, (const byte *)PassPhrase.data(), PassPhrase.size());
    CryptoPP::Integer y(digest, CryptoPP::SHA256::DIGESTSIZE);

    GlobalPrivateKey.Initialize(CryptoPP::ASN1::secp256k1(), y);
    GlobalPrivateKey.MakePublicKey(GlobalPublicKey);
}

void GenerateWaitTimerKey(void)
{
    WaitTimerPrivateKey.Initialize(prng, CryptoPP::ASN1::secp256k1());
    WaitTimerPrivateKey.MakePublicKey(WaitTimerPublicKey);
}

string SignMessage(CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PrivateKey privkey, string message)
{
    CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::Signer signer(privkey);

    // Compute the digest of the message
    unsigned char digest[CryptoPP::SHA256::DIGESTSIZE];
    CryptoPP::SHA256().CalculateDigest(digest, (const byte *)message.data(), message.size());

    // Sign, and trim signature to actual size
    size_t siglen = signer.MaxSignatureLength();
    string signature(siglen, 0x00);

    siglen = signer.SignMessage(prng, (const byte *)digest, CryptoPP::SHA256::DIGESTSIZE, (byte *)signature.data());
    signature.resize(siglen);

#if ENCODESIGNATURE
    return B32Encode(signature);
#else
    return signature;
#endif
}

bool verify_signature(CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::PublicKey pubkey, string message, string signature)
{
    CryptoPP::ECDSA<CryptoPP::ECP, CryptoPP::SHA1>::Verifier verifier(pubkey);

    // Compute the digest of the message
    unsigned char digest[CryptoPP::SHA256::DIGESTSIZE];
    CryptoPP::SHA256().CalculateDigest(digest, (const byte *)message.data(), message.size());

#if ENCODESIGNATURE
    string decoded = B32Decode(signature);
    return verifier.VerifyMessage((const byte *)digest, CryptoPP::SHA256::DIGESTSIZE, (const byte *)decoded.data(), decoded.size());
#else
    // This is the unencoded version
    return verifier.VerifyMessage((const byte *)digest, CryptoPP::SHA256::DIGESTSIZE, (const byte *)signature.data(), signature.size());
#endif
}

double CurrentTime(void)
{
#if _WIN32
    SYSTEMTIME st_epoc;
    FILETIME ft_epoc;
    ULARGE_INTEGER epoc;
    SYSTEMTIME st_now;
    FILETIME ft_now;
    ULARGE_INTEGER now;
    ULARGE_INTEGER now_since_epoc;
    long now_seconds;

    st_epoc.wYear = 1970;
    st_epoc.wMonth = 1;
    st_epoc.wDay = 1;
    st_epoc.wDayOfWeek = 4;
    st_epoc.wHour = 0;
    st_epoc.wMinute = 0;
    st_epoc.wSecond = 0;
    st_epoc.wMilliseconds = 0;

    SystemTimeToFileTime(&st_epoc, &ft_epoc);
    epoc.LowPart = ft_epoc.dwLowDateTime;
    epoc.HighPart = ft_epoc.dwHighDateTime;

    GetSystemTime(&st_now);
    SystemTimeToFileTime(&st_now, &ft_now);
    now.LowPart = ft_now.dwLowDateTime;
    now.HighPart = ft_now.dwHighDateTime;

    now_since_epoc.QuadPart = now.QuadPart - epoc.QuadPart;

    now_seconds = (long) (now_since_epoc.QuadPart / 10000000L);
    return now_seconds + st_now.wMilliseconds / 1000.0;
#else
    struct timeval now;
    gettimeofday(&now, NULL);

    return now.tv_sec + now.tv_usec / 1000000.0;
#endif
}

string CreateIdentifier(string signature)
{
    // Compute the digest of the message
    unsigned char digest[CryptoPP::SHA256::DIGESTSIZE];
    CryptoPP::SHA256().CalculateDigest(digest, (const byte *)signature.data(), signature.size());
    
    CryptoPP::Base32Encoder encoder(NULL, false);
    encoder.Put((byte *)digest, CryptoPP::SHA256::DIGESTSIZE);
    encoder.MessageEnd();

    string encoded;
    encoded.resize(encoder.MaxRetrievable());
    encoder.Get((byte *)encoded.data(), encoded.size());

    return encoded.substr(0,16);
}

string B32Encode(string message)
{
    CryptoPP::Base32Encoder encoder(NULL, false);
    encoder.Put((byte *)message.data(), message.size());
    encoder.MessageEnd();

    string encoded;
    encoded.resize(encoder.MaxRetrievable());
    encoder.Get((byte *)encoded.data(), encoded.size());

    return encoded;
}

string B32Decode(string encoded)
{
    CryptoPP::Base32Decoder decoder;
    decoder.Put((byte *)encoded.data(), encoded.size());
    decoder.MessageEnd();

    string decoded;
    decoded.resize(decoder.MaxRetrievable());
    decoder.Get((byte *)decoded.data(), decoded.size());

    return decoded;
}

string TestSignMessage(string message)
{
    return SignMessage(GlobalPrivateKey, message);
}

bool TestVerifySignature(string message, string signature)
{
    return verify_signature(GlobalPublicKey, message, signature);
}

void InitializePoetEnclaveModule(void)
{
    GenerateGlobalKey();
    GenerateWaitTimerKey();
}

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

#pragma once

#include <stddef.h>
#include <vector>

#include <sgx_tae_service.h>
#include <sgx_tcrypto.h>

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
class PoetState
{
public:
    PoetState(
        const uint8_t* inSealedState,
        size_t sealedDataLength
        );
    virtual ~PoetState();

    static size_t GetSealedLength();
    void Seal(
        uint8_t* outSealedState,
        size_t inSealedBufferLength
        );
    void Reset();

    uint32_t IncrementCounter();
    uint32_t GetSequenceId();

    // Methods for keeping track of the current wait timer

    void SetCurrentWaitTimer(
        const sgx_ec256_signature_t* inWaitTimerSignature
        );
    void VerifyCurrentWaitTimer(
        const sgx_ec256_signature_t* inWaitTimerSignature
        );
    void ClearCurrentWaitTimer();

    // Methods for keeping track of the public/private key pair (i.e.,
    // signup data)

    void GetKeyPair(
        sgx_ec256_private_t* outPrivateKey,
        sgx_ec256_public_t* outPublicKey
        );
    void SetKeyPair(
        const sgx_ec256_private_t* inPrivateKey,
        const sgx_ec256_public_t* inPublicKey
        );

    const sgx_ec256_private_t* GetPrivateKey();
    void SetPrivateKey(
        const sgx_ec256_private_t* inPrivateKey
        );

    const sgx_ec256_public_t* GetPublicKey();
    void SetPublicKey(
        const sgx_ec256_public_t* inPublicKey
        );

    bool KeyPairIsValid();

private:
    static const uint32_t VERSION = 3;

    typedef struct _State
    {
        uint32_t stateVersion;
        // The SGX monotonic counter ID being used by the enclave.
        sgx_mc_uuid_t counterId;
        // Current monotonic counter value -- used to prevent replay attacks.
        uint32_t counterValue;
        // Indicates if the currentWaitTimerSignature is valid or not.
        bool currentWaitTimerSignatureIsValid;
        // This is the signature of the currently-valid wait timer.  Only valid
        // if waitTimerSignatureIsValid is true.
        sgx_ec256_signature_t currentWaitTimerSignature;
        // Flags to indicate if keys are valid.
        bool privateKeyIsValid;
        bool publicKeyIsValid;
        // The PoET public/private key pair.  Keys are only valid if
        // corresponding flags are true.
        sgx_ec256_private_t privateKey;
        sgx_ec256_public_t publicKey;
    } State;

private:
    std::vector<uint8_t> stateData;
    State* state;
}; // class PoetState

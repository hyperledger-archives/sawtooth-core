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

#include <sgx_tseal.h>
#include <assert.h>
#include "error.h"
#include "zero.h"
#include "poet_state.h"
#include "utils_enclave.h"

namespace sp = sawtooth::poet;

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
// XX Public interface                                               XX
// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
PoetState::PoetState(
    const uint8_t* inSealedState,
    size_t sealedDataLength
    )
{
    sp::ThrowIfNull(inSealedState, "Sealed state pointer is NULL");
    sp::ThrowIf<sp::ValueError>(
        sealedDataLength != this->GetSealedLength(),
        "Sealed state buffer is too small");

    sgx_status_t ret = SGX_SUCCESS;
    sgx_sealed_data_t zeroData = { 0 };

    if (!memcmp(&zeroData, inSealedState, sizeof(sgx_sealed_data_t))) {
        this->stateData.resize(sizeof(State));
        ZeroV(this->stateData);
        this->state = reinterpret_cast<State *>(&this->stateData[0]);
        this->state->stateVersion = this->VERSION;

        ret = 
            sgx_create_monotonic_counter(
                &this->state->counterId,
                &this->state->counterValue);
        sp::ThrowSgxError(ret, "Failed to create monotonic counter.");

        this->state->currentWaitTimerSignatureIsValid = false;
        this->state->privateKeyIsValid = false;
        this->state->publicKeyIsValid = false;
    } else {
        uint32_t unsealedLength =
            sgx_get_encrypt_txt_len(
                reinterpret_cast<const sgx_sealed_data_t *>(inSealedState));

        this->stateData.resize(unsealedLength);
        uint32_t length = unsealedLength;
        ret =
            sgx_unseal_data(
                reinterpret_cast<const sgx_sealed_data_t *>(inSealedState),
                nullptr,
                nullptr,
                &this->stateData[0],
                &length);
        sp::ThrowSgxError(ret, "Failed to unseal state data.");
        this->state = reinterpret_cast<State *>(&this->stateData[0]);

        // check if we have a valid MC
        uint32_t value = 0;
        ret =
            sgx_read_monotonic_counter(
                &this->state->counterId,
                &value);
        if (SGX_ERROR_MC_NOT_FOUND == ret) {
            // This wait timer is no more, create another...
            ZeroV(this->stateData);
            this->state->stateVersion = this->VERSION;

            ret =
                sgx_create_monotonic_counter(
                    &this->state->counterId,
                    &this->state->counterValue);
            sp::ThrowSgxError(ret, "Failed to create monotonic counter.");

            this->state->currentWaitTimerSignatureIsValid = false;
        }
    }

    // Now we have PoetState Object, either newly created or unsealed.
    // Validate that it is valid

    sp::ThrowIf<sp::ValueError>(
        this->VERSION != this->state->stateVersion,
        "Poet State version mismatch.");

    uint32_t value = 0;
    ret = sgx_read_monotonic_counter(&this->state->counterId, &value);
    sp::ThrowSgxError(ret, "Failed to read monotonic counter.");
    sp::ThrowIf<sp::ValueError>(
        value != this->state->counterValue,
        "Poet State Counter mismatch.");
} // PoetState::PoetState

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
PoetState::~PoetState()
{
    if(this->stateData.size()) {
        memset_s(
            &this->stateData[0],
            this->stateData.size(),
            0,
            this->stateData.size());
    }
} // PoetState::~PoetState

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
size_t PoetState::GetSealedLength()
{
    return
        static_cast<size_t>(
            sgx_calc_sealed_data_size(
                0,
                static_cast<uint32_t>(sizeof(State))));
} //PoetState::GetSealedLength

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void PoetState::Seal(
    uint8_t* outSealedState,
    size_t inSealedBufferLength
    )
{

    uint32_t sealedSized =
        sgx_calc_sealed_data_size(
            0,
            static_cast<uint32_t>(this->stateData.size()));

    sp::ThrowIfNull(outSealedState, "Sealed state buffer is NULL");
    sp::ThrowIf<sp::ValueError>(
        inSealedBufferLength != sealedSized,
        "Sealed state buffer is too small");

    sgx_status_t ret =
        sgx_seal_data(
            0,
            nullptr,
            static_cast<uint32_t>(this->stateData.size()),
            &this->stateData[0],
            static_cast<uint32_t>(inSealedBufferLength),
            reinterpret_cast<sgx_sealed_data_t *>(outSealedState));
    sp::ThrowSgxError(ret, "Failed to seal state data.");
} // PoetState::Seal

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void PoetState::Reset()
{
    sgx_status_t ret =
        sgx_destroy_monotonic_counter(
            &this->state->counterId);
    sp::ThrowSgxError(ret, "Failed to destroy monotonic counter.");
    ZeroV(this->stateData);
} // PoetState::Reset

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
uint32_t PoetState::IncrementCounter()
{
    uint32_t value;

    sgx_status_t ret =
        sgx_increment_monotonic_counter(
            &this->state->counterId,
            &value);
    sp::ThrowSgxError(ret, "Failed to increment monotonic counter.");
    this->state->counterValue = value;
    return value;
} // PoetState::IncrementCounter

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
uint32_t PoetState::GetSequenceId()
{
    return this->state->counterValue;
} // PoetState::GetSequenceId

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void PoetState::SetCurrentWaitTimer(
    const sgx_ec256_signature_t* waitTimerSignature
    )
{
    sp::ThrowIfNull(waitTimerSignature, "Wait timer signature is NULL");

    // Copy the wait timer signature and set the valid flag to indicate that
    // there is a currently wait timer.
    memcpy(
        &this->state->currentWaitTimerSignature,
        waitTimerSignature,
        sizeof(this->state->currentWaitTimerSignature));
    this->state->currentWaitTimerSignatureIsValid = true;
} // PoetState::SetCurrentWaitTimer

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void PoetState::VerifyCurrentWaitTimer(
    const sgx_ec256_signature_t* waitTimerSignature
    )
{
    sp::ThrowIfNull(waitTimerSignature, "Wait timer signature is NULL");

    // In order to verify the wait timer, the valid flag just be set and
    // the signatures must match.
    sp::ThrowIf<sp::ValueError>(
        !this->state->currentWaitTimerSignatureIsValid,
        "There is not a current wait timer");
    sp::ThrowIf<sp::ValueError>(
        memcmp(
            &this->state->currentWaitTimerSignature,
            waitTimerSignature,
            sizeof(this->state->currentWaitTimerSignature)) != 0,
        "Wait timer does not match current wait timer");
} // PoetState::VerifyCurrentWaitTimer

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void PoetState::ClearCurrentWaitTimer()
{
    // It is sufficient to simply reset the flag to indicate that the wait
    // timer is not valid.
    this->state->currentWaitTimerSignatureIsValid = false;
} // PoetState::ClearCurrentWaitTimer

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void PoetState::GetKeyPair(
    sgx_ec256_private_t* outPrivateKey,
    sgx_ec256_public_t* outPublicKey
    )
{
    sp::ThrowIfNull(outPrivateKey, "Private key buffer is NULL");
    sp::ThrowIfNull(outPublicKey, "Public key buffer is NULL");

    memcpy(outPrivateKey, this->GetPrivateKey(), sizeof(*outPrivateKey));
    memcpy(outPublicKey, this->GetPublicKey(), sizeof(*outPublicKey));
} // PoetState::GetKeyPair

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void PoetState::SetKeyPair(
    const sgx_ec256_private_t* inPrivateKey,
    const sgx_ec256_public_t* inPublicKey
    )
{
    sp::ThrowIfNull(inPrivateKey, "Private key is NULL");
    sp::ThrowIfNull(inPublicKey, "Public key is NULL");

    this->SetPrivateKey(inPrivateKey);
    this->SetPublicKey(inPublicKey);
} // PoetState::SetKeyPair

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
const sgx_ec256_private_t* PoetState::GetPrivateKey()
{
    return &this->state->privateKey;
} // PoetState::GetPrivateKey

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void PoetState::SetPrivateKey(
    const sgx_ec256_private_t* inPrivateKey
    )
{
    sp::ThrowIfNull(inPrivateKey, "Private key is NULL");

    memcpy(
        &this->state->privateKey,
        inPrivateKey,
        sizeof(this->state->privateKey));
    this->state->privateKeyIsValid = true;
} // PoetState::SetPrivateKey

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
const sgx_ec256_public_t* PoetState::GetPublicKey()
{
    return &this->state->publicKey;
} // PoetState::GetPublicKey

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void PoetState::SetPublicKey(
    const sgx_ec256_public_t* inPublicKey
    )
{
    sp::ThrowIfNull(inPublicKey, "Public key is NULL");

    memcpy(
        &this->state->publicKey,
        inPublicKey,
        sizeof(this->state->publicKey));
    this->state->publicKeyIsValid = true;
} // PoetState::SetPublicKey

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
bool PoetState::KeyPairIsValid()
{
    return this->state->privateKeyIsValid && this->state->publicKeyIsValid;
} // PoetState::KeyPairIsValid

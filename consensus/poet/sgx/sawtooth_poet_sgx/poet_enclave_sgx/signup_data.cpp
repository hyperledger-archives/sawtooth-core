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

#include <vector>

#include "poet_enclave.h"
#include "common.h"
#include "poet.h"

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
_SignupData::_SignupData(
    const std::string& originatorPublicKeyHash
    )
{
    // Create some buffers for receiving the output parameters
    std::vector<char> poetPublicKey(Poet_GetPublicKeySize());
    std::vector<char> pseManifest(Poet_GetPseManifestSize());
    std::vector<char> enclaveQuote(Poet_GetEnclaveQuoteSize());
    std::vector<char> sealedSignupData(Poet_GetSealedSignupDataSize());
    
    // Create the signup data
    poet_err_t result = 
        Poet_CreateSignupData(
            originatorPublicKeyHash.c_str(),
            &poetPublicKey[0],
            poetPublicKey.size(),
            &pseManifest[0],
            pseManifest.size(),
            &enclaveQuote[0],
            enclaveQuote.size(),
            &sealedSignupData[0],
            sealedSignupData.size());
    ThrowPoetError(result);
    
    // Save the output parameters in our properties so that they can
    // be read from Python code
    this->poet_public_key = std::string(&poetPublicKey[0]);
    this->pse_manifest = std::string(&pseManifest[0]);
    this->enclave_quote = std::string(&enclaveQuote[0]);
    this->sealed_signup_data = std::string(&sealedSignupData[0]);
} // _SignupData::_SignupData
    
_SignupData* _SignupData::CreateSignupData(
    const std::string& originatorPublicKeyHash
    )
{
    return new _SignupData(originatorPublicKeyHash);
} // _SignupData::CreateSignupData

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
std::string _SignupData::UnsealSignupData(
    const std::string& sealedSignupData
    )
{
    // Create some buffers for receiving the output parameters
    std::vector<char> poetPublicKey(Poet_GetPublicKeySize());
    
    // Unseal the signup data
    poet_err_t result = 
        Poet_UnsealSignupData(
            sealedSignupData.c_str(),
            &poetPublicKey[0],
            poetPublicKey.size());
    ThrowPoetError(result);
    
    // Return the PoET public key to the caller
    return std::string(&poetPublicKey[0]);
} // _SignupData::UnsealSignupData

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void _SignupData::ReleaseSignupData(
    const std::string& sealedSignupData
    )
{
    // Unseal the signup data
    poet_err_t result =
        Poet_ReleaseSignupData(
            sealedSignupData.c_str());
    ThrowPoetError(result);
} // _SignupData::UnsealSignupData

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
_SignupData* _create_signup_data(
    const std::string& originator_public_key_hash
    )
{
    return
        _SignupData::CreateSignupData(originator_public_key_hash);
} // _create_signup_data

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
std::string unseal_signup_data(
    const std::string& sealed_signup_data
    )
{
    return _SignupData::UnsealSignupData(sealed_signup_data);
} // _unseal_signup_data

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void release_signup_data(
    const std::string& sealed_signup_data
    )
{
    _SignupData::ReleaseSignupData(sealed_signup_data);
} // _unseal_signup_data

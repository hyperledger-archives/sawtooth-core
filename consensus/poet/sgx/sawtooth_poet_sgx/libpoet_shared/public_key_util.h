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

#include <sgx_tcrypto.h>
#include <string>
#include "hex_string.h"

namespace sawtooth {
    namespace poet {
        // Convenience methods for encoding and decoding sgx_ec256_public_t
        // structures.  These methods are used in multiple places and we
        // need to ensure that the keys are encoded and decoded in a consistent
        // manner.

        inline size_t EncodedPublicKeySize()
        {
            // We encode the components of the public key separately to avoid
            // potential for struct alignment issues, so when computing the size
            // use size of individual structure fields.
            return
                HEX_STRING_SIZE(
                    sizeof(static_cast<sgx_ec256_public_t *>(nullptr)->gx) +
                    sizeof(static_cast<sgx_ec256_public_t *>(nullptr)->gy));
        } // EncodedPublicKeySize

        std::string EncodePublicKey(
            const sgx_ec256_public_t* inPublicKey
            );

        void DecodePublicKey(
            sgx_ec256_public_t* outPublicKey,
            const std::string& inEncodedPublicKey
            );

    } // namespace poet
} // namespace sawtooth

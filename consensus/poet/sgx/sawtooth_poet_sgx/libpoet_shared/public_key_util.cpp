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
#include <algorithm>
#include <iterator>

#include "public_key_util.h"
#include "hex_string.h"


namespace sawtooth {
    namespace poet {

        std::string EncodePublicKey(
            const sgx_ec256_public_t* inPublicKey
            )
        {
            // We know that the buffer will be no bigger than
            // sizeof(*inPublicKey) because of potential padding
            std::vector<uint8_t> bigEndianBuffer;
            bigEndianBuffer.reserve(sizeof(*inPublicKey));

            // NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE
            //
            // Before converting the public key to a hex string we are going to
            // reverse the public key gx and gy components as it appears that
            // these large integers seem (I say seem as I don't have access to
            // source code) to be stored in the arrays in little endian.
            // Therefore, we are going to reverse them so that they are in big
            // endian.
            //
            // NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE

            // Copy the gx and gy components of the public key into the the
            // buffer, reversing the order of bytes as we do so.
            std::copy(
                std::reverse_iterator<const uint8_t *>(
                    inPublicKey->gx + sizeof(inPublicKey->gx)),
                std::reverse_iterator<const uint8_t *>(inPublicKey->gx),
                std::back_inserter(bigEndianBuffer));
            std::copy(
                std::reverse_iterator<const uint8_t *>(
                    inPublicKey->gy + sizeof(inPublicKey->gy)),
                std::reverse_iterator<const uint8_t *>(inPublicKey->gy),
                std::back_inserter(bigEndianBuffer));

            // Now convert the key components to a hex string and return the result
            // to the caller
            return BinaryToHexString(bigEndianBuffer);
        } // EncodePublicKey

        void DecodePublicKey(
            sgx_ec256_public_t* outPublicKey,
            const std::string& inEncodedPublicKey
            )
        {
            // First convert the hex string to a buffer of bytes
            std::vector<uint8_t> bigEndianBuffer(HexStringToBinary(inEncodedPublicKey));

            // NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE
            //
            // After converting the public key from a hex string we are going to
            // reverse the public key gx and gy components as it appears that
            // these large integers seem (I say seem as I don't have access to
            // source code) to be stored in the arrays in little endian.
            // Therefore, we are going to reverse them from the big endian
            // format we used when we encoded it.
            //
            // NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE - NOTE

            // Copy the contents of the buffer into the gx and gy components of
            // the public key, reversing the order of the bytes as we do so.
            std::copy(
                std::reverse_iterator<uint8_t *>(
                    &bigEndianBuffer[0] + sizeof(outPublicKey->gx)),
                std::reverse_iterator<uint8_t *>(&bigEndianBuffer[0]),
                outPublicKey->gx);
            std::copy(
                std::reverse_iterator<uint8_t *>(
                    &bigEndianBuffer[sizeof(outPublicKey->gx)] +
                    sizeof(outPublicKey->gy)),
                std::reverse_iterator<uint8_t *>(
                    &bigEndianBuffer[sizeof(outPublicKey->gx)]),
                outPublicKey->gy);
        } // DecodePublicKey

    } // namespace poet
} // namespace sawtooth

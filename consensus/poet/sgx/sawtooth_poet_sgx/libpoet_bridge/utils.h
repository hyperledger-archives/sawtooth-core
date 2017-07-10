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
#include <stdint.h>
#include <string.h>
#include <vector>
#include <string>
#include "poet.h"
#include "error.h"
#include "base64.h"

namespace sawtooth {
    namespace poet {

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        inline void EncodeB64(
            char* outEncodedData,
            size_t inEncodedDataLength,
            const uint8_t* inBinaryData,
            size_t inBinaryDataLength
            )
        {
            std::string b64Buffer =
                base64_encode(
                    inBinaryData,
                    static_cast<unsigned int>(inBinaryDataLength));

            ThrowIf<ValueError>(
                b64Buffer.length() > inEncodedDataLength,
                "Data buffer too small");

            memset(outEncodedData, 0, inEncodedDataLength);
            memcpy(outEncodedData, b64Buffer.data(), b64Buffer.length());
        } // EncodeB64

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        template < typename T >
        inline void EncodeB64(
            char* outEncodedData,
            size_t inEncodedDataLength,
            const T* inBinaryData
            )
        {
            EncodeB64(
                outEncodedData,
                inEncodedDataLength,
                reinterpret_cast<const uint8_t *>(inBinaryData),
                sizeof(T));
        } // EncodeB64

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        inline void EncodeB64(
            char* outEncodedData,
            size_t inEncodedDataLength,
            const std::vector<uint8_t>& inBinaryData
            )
        {
            EncodeB64(
                outEncodedData,
                inEncodedDataLength,
                &inBinaryData[0],
                inBinaryData.size());
        } // EncodeB64

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        inline void DecodeB64(
            std::vector<uint8_t>& outBinaryData,
            const char* inEncodedBuffer
            )
        {
            std::string dataBuffer = base64_decode(inEncodedBuffer);
            outBinaryData.assign(dataBuffer.begin(), dataBuffer.end());
        } // DecodeB64

    } // namespace poet
} // namespace sawtooth

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
#include <string>
#include <vector>

// This macro calculates the length of the actual data portion of the
// hex-string encoding of a buffer with x bytes PLUS the additional byte
// needed for the string terminator.
#define HEX_STRING_SIZE(x) (static_cast<size_t>(((x) * 2) + 1))

namespace sawtooth {
    namespace poet {
        // Convert a hex string (i.e., a string of characters with values
        // between '0'-'9', 'A'-'F') to an array of bytes
        std::vector<uint8_t> HexStringToBinary(
            const std::string& inHexString
            );

        void HexStringToBinary(
            uint8_t* outBinaryData,
            size_t inBinaryDataLength,
            const std::string& inHexString
            );

        // Convert an array of bytes (represented as either a std::vector of
        // bytes or a raw array) to a hex string.
        std::string BinaryToHexString(
            const std::vector<uint8_t>& inBinaryData
            );
        std::string BinaryToHexString(
            const uint8_t* inBinaryData,
            size_t inBinaryDataLength
            );

    } // namespace poet
} // namespace sawtooth

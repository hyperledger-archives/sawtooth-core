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

#include <algorithm>
#include <ctype.h>
#include "hex_string.h"
#include "error.h"

namespace sawtooth {
    namespace poet {

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        static inline uint8_t HexToNibble(
            char hex
            )
        {
            hex = toupper(hex);

            if (hex >= 'A' && hex <= 'F') { // A-F case
                return 10 + (hex - 'A');
            }
            if (hex >= '0' && hex <= '9') { // 0-9 case
                return hex - '0';
            }

            throw ValueError("Hex digit is not valid");
        } // HexToNibble

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        static inline uint8_t HexToByte(
            const char* inHexDigits
            )
        {
            uint8_t c1 = HexToNibble(inHexDigits[0]);
            uint8_t c2 = HexToNibble(inHexDigits[1]);
            return (c1 << 4) | c2;
        } // HexToByte

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        std::vector<uint8_t> HexStringToBinary(
            const std::string& inHexString
            )
        {
            // Create a buffer to hold the binary data and use the array
            // implementation to do the actual conversion
            std::vector<uint8_t> binaryData(inHexString.length() / 2);

            HexStringToBinary(&binaryData[0], binaryData.size(), inHexString);

            return binaryData;
        } // HexStringToBinary

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void HexStringToBinary(
            uint8_t* outBinaryData,
            size_t inBinaryDataLength,
            const std::string& inHexString
            )
        {
            // Verify that the hex string is an even length
            ThrowIf<ValueError>(
                (inHexString.length() % 2) != 0,
                "Hex encoded string is not an even length");

            const char* pHex = inHexString.c_str();
            size_t len = inHexString.length();
            inBinaryDataLength = std::min(inBinaryDataLength, len / 2);
            size_t pos = 0;
            size_t opos = 0;
            while (pos < len && opos < inBinaryDataLength) {
                outBinaryData[opos++] = HexToByte(&pHex[pos]);
                pos += 2;
            }
        } // HexStringToBinary

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        std::string BinaryToHexString(
            const std::vector<uint8_t>& inBinaryData
            )
        {
            return BinaryToHexString(&inBinaryData[0], inBinaryData.size());
        } // BinaryToHexString

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        std::string BinaryToHexString(
            const uint8_t* inBinaryData,
            size_t inBinaryDataLength
            )
        {
            static const char *hexDigits = "0123456789ABCDEF";

            // Create a string and give a hint to its final size (twice the size
            // of the input binary data)
            std::string hexString;
            hexString.reserve(inBinaryDataLength * 2);

            // Run through the binary data and convert to a hex string
            std::for_each(
                inBinaryData,
                inBinaryData + inBinaryDataLength,
                [&hexString](uint8_t inputByte) {
                    hexString.push_back(hexDigits[inputByte >> 4]);
                    hexString.push_back(hexDigits[inputByte & 0x0F]);
                });

            return hexString;
        } // BinaryToHexString

    } // namespace poet
} // namespace sawtooth


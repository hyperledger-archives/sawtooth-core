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
#include "address_mapper.h"

#include <exception>
#include <iostream>
#include <string>

#include "cryptopp/sha.h"
#include "cryptopp/filters.h"
#include "cryptopp/hex.h"
#include "log4cxx/logger.h"

const size_t MERKLE_ADDRESS_LENGTH = 70;
const size_t NAMESPACE_PREFIX_LENGTH = 6;

static log4cxx::LoggerPtr  logger(log4cxx::Logger::getLogger
    ("sawtooth.address_mapper"));

// Helper function to generate an SHA512 hash and return it as a hex
// encoded string.
static std::string SHA512(const std::string& message) {
    std::string digest;
    CryptoPP::SHA512 hash;

    CryptoPP::StringSource hasher(message, true,
        new CryptoPP::HashFilter(hash,
          new CryptoPP::HexEncoder (
             new CryptoPP::StringSink(digest), false)));

    return digest;
}

// Check that a string only contains valid lower case hex characters.
static bool IsHex(const std::string& str) {
    return str.find_first_not_of("0123456789abcdef") ==
        std::string::npos;
}

// Checks if an address string meets the constraints of an address.
// These are that it is exactly 70 characters long and contains only
// lowercase hexadecimal characters.
static void CheckIfValidAddr(const std::string& addr) {
    if (addr.length() != MERKLE_ADDRESS_LENGTH) {
        std::stringstream out;
        out << "Address does not contain 70 "
            << "characters: " << addr.length() << " != 70";
        throw AddressFormatError(out.str());
    } else if (!IsHex(addr)) {
        throw AddressFormatError("Address must contain only " \
            "lowercase hexadecimal characters");
    }
}

// Checks if an address string meets the constraints of an address.
// These are that it is exactly 6 characters long and contains only
// lowercase hexadecimal characters.
static void CheckIfValidNamespace(const std::string& addr) {
    if (addr.length() != NAMESPACE_PREFIX_LENGTH) {
        throw AddressFormatError("Namespace prefix does not contain 6 " \
            "characters");
    } else if (!IsHex(addr)) {
        throw AddressFormatError("Namespace prefix must contain only " \
            "lowercase hexadecimal characters");
    }
}

AddressMapper::AddressMapper(const std::string& namespace_) :
    namespace_initialized(false), namespace_(namespace_) {}

std::string AddressMapper::MapKey(const std::string& key, std::size_t pos, std::size_t count) const {
    return SHA512(key).substr(pos, count);
}

std::string AddressMapper::MapNamespace(const std::string& namespace_) const {
    std::string ns = SHA512(namespace_);
    return ns.substr(0, 6);
}


std::string AddressMapper::GetNamespacePrefix() {
    if (!this->namespace_initialized) {
        this->namespace_prefix = this->MapNamespace(namespace_);
        CheckIfValidNamespace(this->namespace_prefix);
        this->namespace_initialized = true;
    }
    return namespace_prefix;
}

std::string AddressMapper::MakeAddress(const std::string& key, std::size_t pos, std::size_t count) {
    std::string key_part = this->MapKey(key, pos, count);
    std::string addr = this->GetNamespacePrefix() + key_part;
    CheckIfValidAddr(addr);

    return addr;
}



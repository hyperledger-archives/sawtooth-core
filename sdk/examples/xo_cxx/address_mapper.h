/* Copyright 2017 Intel Corporation

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
------------------------------------------------------------------------------*/
#pragma once

#include <memory>
#include <string>

// Raised if any of the addresses generated violate
// the merkel trie address constraints.
class AddressFormatError: public std::runtime_error {
 public:
    explicit AddressFormatError(std::string const& error)
        : std::runtime_error(error)
    {}
};


// Helper class to provide mappings from domain identifiers
// to merkle trie addresses. This class is designed to be overloaded, such
// that implementers of TransactionProcessors can define their own mappings
// from their native object ids to merkle trie addresses.
//
// The default implementation uses a SHA512 hash to map both the key and the
// namespace to the merkle trie address. Collisions in the key mappings should
// be uncommon but still possible, data storage behind the keys.
//
// Each instance of the mapper holds a namespace that is mapped to a
// namespace prefix when it is constructed. If your transaction processor
// operates on multiple namespaces, it is recommended that you use an instance
// for each namespace.
class AddressMapper {
 public:
    // Constructor for an address mapping object, Takes the
    // unencoded namespace name, it will be mapping objects, to as a parameter.
    // The namespace argument passed will be mapped to a namespace_prefix
    AddressMapper(const std::string& namespace_);
    virtual ~AddressMapper() {}

    // Maps an namespace string to an namespace address prefix.
    // this provides a default implementation using SHA512.
    // it is intended to be overridden by subclass implementations
    // that can provide their own mapping of namespace strings to
    // prefixes. The requirements are that the mapping needs to
    // return a prefix that is 6 characters in length and consists
    // of only lower case hexadecimal characters(0123456789abcdef).
    virtual std::string MapNamespace(const std::string& key) const;

    // Maps an key string to a address, this provides a default
    // implementation using SHA512.
    // It is intended to be overridden by subclass implementations
    // that can provide their own mappings. The requirements are that
    // the mapping needs to return a string that is 128 characters
    // in length and consists of only lower case hexadecimal characters.
    virtual std::string MapKey(const std::string& key, std::size_t pos, std::size_t count) const;


    // returns the namespace prefix generated when the class was constructed.
    std::string GetNamespacePrefix();

    // Maps the key passed to the function and concatenates it with the
    // namespace prefix this object was initialized with and returns
    // a fully qualified Merkle Trie address. These addresses are always
    // 134 characters in length and consist entirely of lower case hexadecimal
    // characters(0123456789abcdef).
    std::string MakeAddress(const std::string& key, std::size_t pos, std::size_t count);

 private:
    bool namespace_initialized;
    std::string namespace_;
    std::string namespace_prefix;
};

typedef std::shared_ptr<AddressMapper> AddressMapperPtr;
typedef std::unique_ptr<AddressMapper> AddressMapperUPtr;

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

#include <map>
#include <memory>
#include <list>
#include <string>
#include <unordered_map>
#include <vector>

namespace sawtooth {

// Utility types to allow for managed instances of std::string on the heap.
typedef std::unique_ptr<std::string> StringUPtr;
typedef std::shared_ptr<std::string> StringPtr;


enum TxHeaderField
{
    TxHeaderBatcherPublicKey = 1,
    TxHeaderStringDependencies,
    TxHeaderFamilyName,
    TxHeaderFamilyVersion,
    TxHeaderInputs,
    TxHeaderNonce,
    TxHeaderOutputs,
    TxHeaderPayloadSha512,
    TxHeaderSignerPublicKey
};

class TxHeaderIF
{
public:
    virtual ~TxHeaderIF(){};

    virtual int GetCount(TxHeaderField field) = 0;
    virtual const ::std::string& GetValue(TxHeaderField field, int index = 0) = 0;
};

typedef std::unique_ptr<TxHeaderIF> TxHeaderUPtr;
typedef std::shared_ptr<TxHeaderIF> TxHeaderPtr;

// The transaction data for a Transaction Processing request.
class Transaction final {
 public:
    Transaction(TxHeaderPtr header, StringPtr payload, StringPtr signature):
            header_(header), payload_(payload), signature_(signature) {
    }

    Transaction (const Transaction&) = delete;
    Transaction (const Transaction&&) = delete;
    Transaction& operator= (const Transaction&) = delete;

    const TxHeaderPtr header() const {
        return this->header_;
    }

    const std::string& payload() const {
        return *(this->payload_);
    }

    const std::string& signature() const {
        return *(this->signature_);
    }

 private:
    TxHeaderPtr header_;
    StringPtr payload_;
    StringPtr signature_;
};
typedef std::unique_ptr<Transaction> TransactionUPtr;


// Provides access to the global state
class GlobalStateIF {
 public:
    typedef std::pair<std::string, std::string> KeyValue;

    virtual ~GlobalStateIF() {}

    // Retrieve a single value from global state. If you are retrieving
    // multiple values, it is encouraged to use the batch get overload defined
    // below. The function returns false if the value is not retrieved, true if
    // it is found in the GlobalStore, and throws an exception if an error occurs
    virtual bool GetState(std::string* out_value, const std::string& address) const = 0;

    // Retrieve multiple values from the global state. Values are returned in
    // the out_values map. If a value is not present then there will be no
    // entry in the returned map. So you must check for the presence of a
    // returned value prior to accessing it.
    virtual void GetState(std::unordered_map<std::string, std::string>* out_values,
        const std::vector<std::string>& addresses) const = 0;

    // Set a single GlobalState value. Use the batch Set function defined
    // below if you are setting multiple items.
    virtual void SetState(const std::string& address, const std::string& value) const = 0;

    // Set multiple values in the global state. Each entry in the addresses
    // param is a std::pair, with the first value representing the address and
    // the second the value.
    //      std::vector<GlobalState::KeyValue> addresses;
    //      addresses.push(std::make_pair(address, value));
    virtual void SetState(const std::vector<KeyValue>& addresses) const = 0;

    // Delete a single GlobalState value. Used the batch Delete function
    // defined below if you are deleting multiple items.
    virtual void DeleteState(const std::string& address) const = 0;

    // Delete multiple entries from global state.
    virtual void DeleteState(const std::vector<std::string>& address) const = 0;
};
typedef std::shared_ptr<GlobalStateIF> GlobalStatePtr;
typedef std::unique_ptr<GlobalStateIF> GlobalStateUPtr;


// TransactionApplicator is an interface that defined to represent the
// processing of a single transaction. This object should make no assumptions
// about the thread and timing of when it will execute. The
// TransactionApplicator owns the reference to the transaction and the global
// state it is passed.
class TransactionApplicator {
 public:
    TransactionApplicator(sawtooth::TransactionUPtr txn,
        sawtooth::GlobalStateUPtr state) : txn(std::move(txn)),
        state(std::move(state)) {}
    virtual ~TransactionApplicator() {}


    // Process the transaction, this function should do all of the processing
    // of the given transaction. The general framework should be:
    // 1) Validate the transaction
    // 2) retrieve the state from GlobalState
    // 3) validate the transaction changes are valid
    // 4) Write the updated state to GlobalState
    //
    // Any exception thrown from this function will result in the transaction
    // being marked as invalid.
    virtual void Apply() = 0;
 protected:
    sawtooth::TransactionUPtr txn;
    sawtooth::GlobalStateUPtr state;
};
typedef std::unique_ptr<TransactionApplicator> TransactionApplicatorUPtr;



// Definition of a TransactionHandler to be registered with the validator.
// Every Transaction Processor should register at least one of these. This
// definition allows for the handler to declare multiple version.
// that it supports.
class TransactionHandler {
 public:
    virtual ~TransactionHandler() {};

    virtual std::string transaction_family_name() const = 0;
    virtual std::list<std::string> versions() const = 0;
    virtual std::list<std::string> namespaces() const = 0;
    // When a Transaction processing reqquest is received, the
    // TransactionHandler is called with the Transaction and the GlobalState
    // context to be processed. The Handler should return a subclassed instance
    // of TransactionApplicator that will handle the processing. As little work
    // as possible should be done in this function.
    virtual TransactionApplicatorUPtr GetApplicator(
        TransactionUPtr txn,
        GlobalStateUPtr state) = 0;
};
typedef std::unique_ptr<TransactionHandler> TransactionHandlerUPtr;
typedef std::shared_ptr<TransactionHandler> TransactionHandlerPtr;


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
class AddressMapperIF {
 public:

    virtual ~AddressMapperIF() {}

    // Maps an namespace string to an namespace address prefix.
    // this provides a default implementation using SHA512.
    // it is intended to be overridden by subclass implementations
    // that can provide their own mapping of namespace strings to
    // prefixes. The requirements are that the mapping needs to
    // return a prefix that is 6 characters in length and consists
    // of only lower case hexadecimal characters(0123456789abcdef).
    virtual std::string MapNamespace(const std::string& key) const = 0;

    // Maps an key string to a address, this provides a default
    // implementation using SHA512.
    // It is intended to be overridden by subclass implementations
    // that can provide their own mappings. The requirements are that
    // the mapping needs to return a string that is 128 characters
    // in length and consists of only lower case hexadecimal characters.
    virtual std::string MapKey(const std::string& key) const = 0;


    // returns the namespace prefix generated when the class was constructed.
    virtual std::string GetNamespacePrefix() = 0;

    // Maps the key passed to the function and concatenates it with the
    // namespace prefix this object was initialized with and returns
    // a fully qualified Merkle Trie address. These addresses are always
    // 134 characters in length and consist entirely of lower case hexadecimal
    // characters(0123456789abcdef).
    virtual std::string MakeAddress(const std::string& key) = 0;


    static AddressMapperIF* Create(const std::string& namespace_);
};

typedef std::shared_ptr<AddressMapperIF> AddressMapperPtr;
typedef std::unique_ptr<AddressMapperIF> AddressMapperUPtr;



class TxProcessorIF
{
public:
   virtual ~TxProcessorIF(){};

    // Called to register the TransactionHandlers defined by your Transaction
    // Processor.  All the TransactionHandler objects must be registered
    // before run is called.
    virtual void RegisterHandler(TransactionHandlerUPtr handler) = 0;

    // The main entry point for the TransactionProcessor. It will not return
    // until the TransactionProcessor shuts down.
    virtual void Run() = 0;

    static TxProcessorIF* Create(const std::string& connection_string);
};
typedef std::unique_ptr<TxProcessorIF> TransactionProcessorUPtr;
typedef std::shared_ptr<TxProcessorIF> TransactionProcessorPtr;

}  // namespace sawtooth

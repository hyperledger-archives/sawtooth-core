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


enum TransactionHeaderField {
    TransactionHeaderBatcherPublicKey = 1,
    TransactionHeaderStringDependencies,
    TransactionHeaderFamilyName,
    TransactionHeaderFamilyVersion,
    TransactionHeaderInputs,
    TransactionHeaderNonce,
    TransactionHeaderOutputs,
    TransactionHeaderPayloadSha512,
    TransactionHeaderSignerPublicKey
};

class TransactionHeader {
public:
    virtual ~TransactionHeader(){};

    virtual int GetCount(TransactionHeaderField field) = 0;
    virtual const ::std::string& GetValue(TransactionHeaderField field, int index = 0) = 0;
};

typedef std::unique_ptr<TransactionHeader> TransactionHeaderUPtr;
typedef std::shared_ptr<TransactionHeader> TransactionHeaderPtr;

// The transaction data for a Transaction Processing request.
class Transaction final {
 public:
    Transaction(TransactionHeaderPtr header, StringPtr payload, StringPtr signature):
            header_(header), payload_(payload), signature_(signature) {
    }

    Transaction (const Transaction&) = delete;
    Transaction (const Transaction&&) = delete;
    Transaction& operator= (const Transaction&) = delete;

    const TransactionHeaderPtr header() const {
        return this->header_;
    }

    const std::string& payload() const {
        return *(this->payload_);
    }

    const std::string& signature() const {
        return *(this->signature_);
    }

 private:
    TransactionHeaderPtr header_;
    StringPtr payload_;
    StringPtr signature_;
};
typedef std::unique_ptr<Transaction> TransactionUPtr;


// Provides access to the global state
class GlobalState {
 public:
    typedef std::pair<std::string, std::string> KeyValue;

    virtual ~GlobalState() {}

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
typedef std::shared_ptr<GlobalState> GlobalStatePtr;
typedef std::unique_ptr<GlobalState> GlobalStateUPtr;


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



class TransactionProcessor {
public:
   virtual ~TransactionProcessor(){};

    // Called to register the TransactionHandlers defined by your Transaction
    // Processor.  All the TransactionHandler objects must be registered
    // before run is called.
    virtual void RegisterHandler(TransactionHandlerUPtr handler) = 0;

    // The main entry point for the TransactionProcessor. It will not return
    // until the TransactionProcessor shuts down.
    virtual void Run() = 0;

    static TransactionProcessor* Create(const std::string& connection_string);
};
typedef std::unique_ptr<TransactionProcessor> TransactionProcessorUPtr;
typedef std::shared_ptr<TransactionProcessor> TransactionProcessorPtr;

}  // namespace sawtooth

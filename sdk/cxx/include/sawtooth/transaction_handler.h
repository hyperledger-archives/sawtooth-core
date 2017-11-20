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

#include "proto/transaction.pb.h"

#include "sawtooth/global_state.h"

namespace sawtooth {

// Utility types to allow for managed instances of std::string on the heap.
typedef std::unique_ptr<std::string> StringUPtr;
typedef std::shared_ptr<std::string> StringPtr;

// The transaction data for a Transaction Processing request.
class Transaction final {
 public:
    Transaction(TransactionHeader* header, StringPtr payload, StringPtr signature):
            payload_(payload), signature_(signature) {
    }

    Transaction (const Transaction&) = delete;
    Transaction (const Transaction&&) = delete;
    Transaction& operator= (const Transaction&) = delete;

    const TransactionHeader& header() const {
        return this->header_;
    }

    const std::string& payload() const {
        return *(this->payload_);
    }

    const std::string& signature() const {
        return *(this->signature_);
    }

 private:
    TransactionHeader header_;
    StringPtr payload_;
    StringPtr signature_;
};
typedef std::unique_ptr<Transaction> TransactionUPtr;


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

}  // namespace sawtooth

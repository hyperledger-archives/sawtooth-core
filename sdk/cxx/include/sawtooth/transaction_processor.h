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
#include <string>

#include "sawtooth_sdk.h"
#include "sawtooth/transaction_handler.h"
#include "sawtooth/message_dispatcher.h"

namespace sawtooth {

// The main processing class for the Sawtooth SDK.
class TransactionProcessorImpl: public TransactionProcessor {
 public:
    // Pass a valid ZMQ connection string for the Validator interconnect
    // address
    explicit TransactionProcessorImpl(const std::string& connection_string);
    virtual ~TransactionProcessorImpl();
    // Called to register the TransactionHandlers defined by your Transaction
    // Processor.  All the TransactionHandler objects must be registered
    // before run is called.
    void RegisterHandler(TransactionHandlerUPtr handler);

    // The main entry point for the TransactionProcessor. It will not return
    // until the TransactionProcessor shuts down.
    void Run();

 private:
    void Register();
    void UnRegister();
    void HandleProcessingRequest(const void* msg,
        size_t msg_size,
        const std::string& correlation_id);

    bool run;
    std::string connection_string;
    MessageDispatcher message_dispatcher;
    MessageStreamPtr response_stream;

    std::map<std::string, TransactionHandlerPtr> handlers;
};

}  // namespace sawtooth


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

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <unordered_map>
#include <memory>
#include <thread>
#include <string>
#include <vector>

#include <zmqpp/context.hpp>
#include <zmqpp/socket.hpp>

#include "sawtooth/message_stream.h"

namespace sawtooth {

// Main message processing handler. This object owns the ZMQ socket connection
// to the validator as well as the internal routing sockets to route messages
// to the main thread for processing and listens for messages to route back to
// the validator.
class MessageDispatcher {
 public:
    // Connect to the validator, create and bind to the internal routing sockets, and route the messages.
    void Connect(const std::string& connection_string);
    // Close all the open sockets and shutdown the message routing thread.
    void Close();

    // Creates a MessageStream object to allow processors(via GlobalState) to
    // submit messages to be routed back to the validator.
    MessageStreamPtr CreateStream();
    zmqpp::context& context() { return this->context_; }
 protected:
    friend class TransactionProcessor;
    MessageDispatcher();

 private:
    void ReceiveMessage();
    void SendMessage();

    void DispatchThread();

    zmqpp::context context_;
    zmqpp::socket server_socket;
    zmqpp::socket message_socket;  // inproc socket to receive messages to
    // route to the validator
    zmqpp::socket processing_request_socket;  // inproc socket to send
    // processing requests to the Transaction Processing
    // thread(the main thread)

    // Synchronization variables to coordinate with MessageStreams and the
    // dispatch thread.
    std::condition_variable condition;
    std::mutex mutex;
    std::atomic<bool> run;
    bool thread_ready;

    std::unordered_map<std::string, std::shared_ptr<FutureMessage>> message_futures;

    std::thread dispatch_thread;
};

}  // namespace sawtooth

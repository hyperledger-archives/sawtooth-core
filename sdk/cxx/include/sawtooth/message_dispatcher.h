
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
    virtual ~MessageDispatcher();

    // Connect to the validator, create and bind to the internal routing sockets, and route the messages.
    void Connect(const std::string& connection_string);
    // Close all the open sockets and shutdown the message routing thread.
    void Close();

    // Creates a MessageStream object to allow processors(via GlobalState) to
    // submit messages to be routed back to the validator.
    MessageStreamPtr CreateStream();
    zmqpp::context& context() { return this->context_; }

    // These are the types we will put in the message we send to the transaction
    // processor when we detect that the server has connected/disconnected.
    // These assume that there will never be transaction processing message type
    // in this range.
    static const Message::MessageType SERVER_CONNECT_EVENT =
        static_cast<Message::MessageType>(0xFFFE);
    static const Message::MessageType SERVER_DISCONNECT_EVENT =
        static_cast<Message::MessageType>(0xFFFF);
 protected:
    friend class TransactionProcessorImpl;
    MessageDispatcher();

 private:
    void ReceiveMessage();
    void SendMessage();
    void HandleConnectionChange();
    uint16_t GetServerSocketEvent(
        zmqpp::socket& server_monitor_socket
        );

    void DispatchThread();

    zmqpp::context context_;
    zmqpp::socket server_socket;
    zmqpp::socket message_socket;  // inproc socket to receive messages to
    // route to the validator
    zmqpp::socket processing_request_socket;  // inproc socket to send
    // processing requests to the Transaction Processing
    // thread(the main thread)

    // Socket for inter-thread communication with the dispatch thread
    static const std::string DISPATCH_THREAD_ENDPOINT;
    zmqpp::socket dispatch_thread_socket;

    bool server_is_connected;

    // The monitor endpoint and socket to poll for server socket events
    static const std::string SERVER_MONITOR_ENDPOINT;
    zmqpp::socket server_monitor_socket;

    // Synchronization variables to coordinate with MessageStreams and the
    // dispatch thread.
    std::mutex mutex;

    std::unordered_map<std::string, std::shared_ptr<FutureMessage>> message_futures;

    std::thread dispatch_thread;

    // Messages that are sent between threads in message dispatcher
    static const std::string THREAD_READY_MESSAGE;
    static const std::string THREAD_EXIT_MESSAGE;
};

}  // namespace sawtooth

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

#include <exception>
#include <iostream>
#include <string>
#include <thread>

#include <log4cxx/logger.h>
#include <zmqpp/context.hpp>
#include <zmqpp/poller.hpp>
#include <zmqpp/socket.hpp>
#include <zmqpp/socket_types.hpp>
#include <zmqpp/socket_options.hpp>

#include "sawtooth/message_dispatcher.h"


namespace sawtooth {

static log4cxx::LoggerPtr logger(log4cxx::Logger::getLogger
    ("sawtooth.MessageDispatcher"));

MessageDispatcher::MessageDispatcher():
        context_(),
        server_socket(this->context_, zmqpp::socket_type::dealer),
        message_socket(this->context_, zmqpp::socket_type::dealer),
        processing_request_socket(this->context_, zmqpp::socket_type::dealer)
        { }

// Connect to the validator component endpoint socket and
// create thread to service the socket, an internal socket is
// also created to receive messages to be forwarded to the validator.
void MessageDispatcher::Connect(const std::string& connection_string) {
    LOG4CXX_INFO(logger, "Connecting to " << connection_string);
    bool connected = false;
    do {
        try {
            this->server_socket.connect(connection_string.c_str());
            connected = true;
        } catch(std::exception e) {
            LOG4CXX_DEBUG(logger, "Connection to validator failed, "
                << "waiting to retry: " << e.what());
            std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        }
    } while (!connected);

    this->message_socket.bind("inproc://send_queue");
    this->processing_request_socket.bind("inproc://request_queue");

    // start the thread to process incoming messages
    this->dispatch_thread = std::thread(MessageDispatcher::DispatchThread,
        this);
    std::unique_lock<std::mutex> lock(this->mutex);
    while (!this->thread_ready) {
        this->condition.wait(lock);
    }
}

void MessageDispatcher::Close() {
    // signal the dispatch thread to stop and join.
    this->run = false;
    this->dispatch_thread.join();

    this->server_socket.close();
    this->message_socket.close();
    this->processing_request_socket.close();
}

void MessageDispatcher::ReceiveMessage() {
    zmqpp::message zmsg;
    this->server_socket.receive(zmsg);

    MessageUPtr msg_proto(new Message());
    msg_proto->ParseFromArray(zmsg.raw_data(0), zmsg.size(0));

    LOG4CXX_DEBUG(logger, "ReceiveMessage MessageType: "
        << msg_proto->message_type());

    if (msg_proto->message_type()
            == Message_MessageType_TP_PROCESS_REQUEST) {
        zmqpp::message out_zmsg;
        const std::string& content = msg_proto->content();
        out_zmsg.add(content.data(), content.length());
        this->processessing_request_socket.send(out_zmsg);
    } else {
        std::unique_lock<std::mutex> lock(this->mutex);
        const std::string& correlation_id = msg_proto->correlation_id();
        auto iter = this->message_futures.find(correlation_id);
        if (iter != this->message_futures.end()) {
            iter->second->SetMessage(std::move(msg_proto));
            this->message_futures.erase(iter);
        } else {
            LOG4CXX_DEBUG(logger, "Received Message without matching "
                << "corrrelation_id:" << correlation_id);
        }
    }
}

void MessageDispatcher::SendMessage() {
    zmqpp::message message;
    this->message_socket.receive(message);
    this->server_socket.send(message);
}

MessageStreamPtr MessageDispatcher::CreateStream() {
    return std::shared_ptr<MessageStream>(new MessageStream(&this->context_,
        this->message_futures, this->mutex));
}

void MessageDispatcher::DispatchThread(MessageDispatcher* dispatcher) {
    zmqpp::poller socket_poller;
    socket_poller.add(dispatcher->server_socket);
    socket_poller.add(dispatcher->message_socket);

    {
        std::unique_lock<std::mutex> lock(dispatcher->mutex);
        dispatcher->thread_ready = true;
        dispatcher->condition.notify_all();
    }

    while (dispatcher->run) {
        socket_poller.poll();
        if (socket_poller.has_input(dispatcher->server_socket)) {
            dispatcher->ReceiveMessage();
        }
        if (socket_poller.has_input(dispatcher->message_socket)) {
            dispatcher->SendMessage();
        }
    }
}

}  // namespace sawtooth

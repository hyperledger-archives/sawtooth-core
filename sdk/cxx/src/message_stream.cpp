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

#include "log4cxx/logger.h"

#include <zmqpp/context.hpp>
#include <zmqpp/socket.hpp>
#include <zmqpp/socket_types.hpp>

#include "sawtooth/message_stream.h"

#include "proto/validator.pb.h"

namespace sawtooth {

static log4cxx::LoggerPtr logger(log4cxx::Logger::getLogger
    ("sawtooth.MessageStream"));

std::atomic<int> MessageStream::correlation_counter(0);

MessageStream::MessageStream(zmqpp::context* context,
        std::unordered_map<std::string, std::shared_ptr<FutureMessage>>& future_message_,
        std::mutex& future_message_mutex_):
        context_(context), 
        future_message_map(future_message_),
        future_message_mutex(future_message_mutex_) {
    
}


void MessageStream::Send(Message::MessageType type,
        const std::string& data,
        const std::string& correlation_id) {
    Message msg;
    std::string msg_data;
    msg.set_message_type(type);
    msg.set_correlation_id(correlation_id);
    msg.set_content(data);
    msg.SerializeToString(&msg_data);

    zmqpp::message message;
    message.add(msg_data.data(), msg_data.length());

    if (!this->socket) {
        this->socket = std::unique_ptr<zmqpp::socket>(
            new zmqpp::socket(*context_, zmqpp::socket_type::dealer));
        this->socket->connect("inproc://send_queue");
    }
    this->socket->send(message);
}


std::string MessageStream::GenerateCorrelationId() const {
    std::stringstream out;
    out << ++(this->correlation_counter);
    return out.str();
}

}  // namespace sawtooth

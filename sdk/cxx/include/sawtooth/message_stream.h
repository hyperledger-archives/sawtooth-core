
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
#include <cstdint>
#include <unordered_map>
#include <memory>
#include <queue>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include <zmqpp/context.hpp>
#include <zmqpp/message.hpp>
#include <zmqpp/socket.hpp>

#include "proto/validator.pb.h"

#include "sawtooth/future_message.h"


namespace sawtooth {

// The MessageStream provides a conduit for messages between the Transaction
// processing instance and the validator. MessageStreams are closely tied to
// the MessageDispatcher, the two objects coordinate the mapping of message
// responses thru a number of shared state objects. As such MessageStreams
// should only be created by the MessageDispatcher via the CreateStream method.
class MessageStream {
 public:
    virtual ~MessageStream() {}

    // Send a message to the validator and get back the FutureMessage object
    // that will receive the response.
    FutureMessagePtr Send(Message::MessageType type,
        const std::string& data);

    // This is a helper function that takes care of serializing a protobuffer
    // defined class and then sending the serialized results to the validator.
    template <typename T>
    FutureMessagePtr SendMessage(Message::MessageType type, const T& proto) {
        std::stringstream proto_stream;
        proto.SerializeToOstream(&proto_stream);
        return this->Send(type, proto_stream.str());
    }

 private:
    friend class MessageDispatcher;
    explicit MessageStream(zmqpp::context* context,
        std::unordered_map<std::string, std::shared_ptr<FutureMessage>>&,
        std::mutex& future_message_mutex);

    std::string GenerateCorrelationId() const;

    zmqpp::context* context_;
    std::unique_ptr<zmqpp::socket> socket;

    std::unordered_map<std::string, std::shared_ptr<FutureMessage>>& future_message_map;
    std::mutex& future_message_mutex;

    static std::atomic<int> correlation_counter;
};

typedef std::shared_ptr<MessageStream> MessageStreamPtr;

}  // namespace sawtooth


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

#include <condition_variable>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

namespace sawtooth {

// Utility types to provide memory management of the Protobuffer defined
// Message class.
typedef std::shared_ptr<Message> MessagePtr;
typedef std::unique_ptr<Message> MessageUPtr;

// FutureMessage is a promise of completion for a message to be delivered.
// This is used internally in the sdk to match responses from the validator
// to the sender.
class FutureMessage final {
 public:
    explicit FutureMessage(const std::string in_correlation_id):
        correlation_id_(in_correlation_id), msg(nullptr) {}
    virtual ~FutureMessage() {}

    FutureMessage (const FutureMessage&) = delete;
    FutureMessage (const FutureMessage&&) = delete;
    FutureMessage& operator= (const FutureMessage&) = delete;

    // Retrieve the message correlation Id.
    std::string correlation_id() const {
        return this->correlation_id_;
    }

    // Check if the response message has been delivered. This can be used to
    // check if GetMessage will block or not.
    bool HasResponse() const {
        return this->msg != nullptr;
    }

    // Get the message response and decode it into the corresponding
    // proto buffer type. This function will block until the message is
    // available. Use HasResponse to test if the message has been delivered.
    template<typename T>
    void GetMessage(Message::MessageType msg_type, T* proto) {
        std::unique_lock<std::mutex> lock(this->mutex);
        if (!this->msg) {
            while (!this->msg) {
                this->condition.wait(lock);
            }
        }
        if (this->msg->message_type() != msg_type) {
            std::stringstream error;
            error << "Error unexpected message response type Expected:"
                << msg_type << " got: " << this->msg->message_type();
            throw std::runtime_error(error.str());
        }
        const std::string& msg_data = this->msg->content();
        proto->ParseFromArray(msg_data.c_str(), msg_data.length());
    }

    // Set the response message and signal any potential waiters that it has
    // been received. The futureMessage takes ownership of the messages.
    void SetMessage(MessageUPtr msg) {
        std::unique_lock<std::mutex> lock(this->mutex);
        this->msg = std::move(msg);
        this->condition.notify_all();
    }

 private:
    std::string correlation_id_;  // The correlation id of the message
    std::condition_variable condition;  // the condition that is signaled when
    // the message arrives.
    std::mutex mutex;  // the mutex to use with the condition variable.
    MessageUPtr msg;  // The message data, set once it has arrives. Owned by
    // this object.
};

typedef std::shared_ptr<FutureMessage> FutureMessagePtr;

}  // namespace sawtooth

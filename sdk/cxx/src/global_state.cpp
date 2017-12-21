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
#include <string>

#include <log4cxx/logger.h>
#include "proto/state_context.pb.h"

#include "sawtooth/global_state.h"
#include "exceptions.h"

namespace sawtooth {

static log4cxx::LoggerPtr  logger(log4cxx::Logger::getLogger
    ("sawtooth.GlobalState"));


GlobalStateImpl::GlobalStateImpl(
    const MessageStreamPtr& message_stream, const std::string& context_id):
    message_stream(message_stream), context_id(context_id) {}

bool GlobalStateImpl::GetState(std::string* out_value, const std::string& address) const {
    std::unordered_map<std::string, std::string> out;
    std::vector<std::string> addresses = { address };

    this->GetState(&out, addresses);
    auto value = out.find(address);
    if( value != out.end()) {
        *out_value = (*value).second;
        return true;
    }
    return false;
}

void GlobalStateImpl::GetState(
        std::unordered_map<std::string, std::string>* out_values,
        const std::vector<std::string>& addresses) const {
    if (!out_values) {
        throw std::runtime_error("Expecting valid pointer passed to " \
            "out_values");
    }
    // create a reference to provide easier access to the return value
    std::unordered_map<std::string, std::string>& out_values_ref(*out_values);
    out_values_ref.clear();

    TpStateGetRequest request;
    TpStateGetResponse response;
    request.set_context_id(this->context_id);
    for (auto addr : addresses) {
      request.add_addresses(addr);
    }

    FutureMessagePtr future = this->message_stream->SendMessage(
        Message::TP_STATE_GET_REQUEST, request);
    future->GetMessage(Message::TP_STATE_GET_RESPONSE, &response);

    if(response.status() == TpStateGetResponse::AUTHORIZATION_ERROR){
        std::stringstream error;
        error << "State Get Authorization error. Check transaction inputs.";
        throw sawtooth::InvalidTransaction(error.str());
    }

    if ( response.entries_size() > 0 ) {
        for (const auto& entry : response.entries()) {
            out_values_ref[entry.address()] = entry.data();
        }
    }
}

void GlobalStateImpl::SetState(const std::string& address, const std::string& value) const {
    std::vector<KeyValue> kv_pairs = { make_pair(address, value) };
    this->SetState(kv_pairs);
}

void GlobalStateImpl::SetState(const std::vector<KeyValue>& kv_pairs) const {
    TpStateSetRequest request;
    TpStateSetResponse response;
    request.set_context_id(this->context_id);
    for (auto kv : kv_pairs) {
        TpStateEntry* ent = request.add_entries();
        ent->set_address(kv.first);
        ent->set_data(kv.second);
    }

    FutureMessagePtr future = this->message_stream->SendMessage(
        Message::TP_STATE_SET_REQUEST, request);
    future->GetMessage(Message::TP_STATE_SET_RESPONSE, &response);

    if(response.status() == TpStateSetResponse::AUTHORIZATION_ERROR){
        std::stringstream error;
        error << "State Set Authorization error. Check transaction outputs.";
        throw sawtooth::InvalidTransaction(error.str());
    }

}


void GlobalStateImpl::DeleteState(
        const std::string& address) const {
    std::vector<std::string> addrs = { address };
    this->DeleteState(addrs);
}

void GlobalStateImpl::DeleteState(const std::vector<std::string>& addresses) const {
    TpStateDeleteRequest request;
    TpStateDeleteResponse response;
    request.set_context_id(this->context_id);
    for (auto& addr : addresses) {
        request.add_addresses(addr);
    }

    FutureMessagePtr future = this->message_stream->SendMessage(
        Message::TP_STATE_DELETE_REQUEST, request);
    future->GetMessage(Message::TP_STATE_DELETE_RESPONSE, &response);
}

}  // namespace sawtooth


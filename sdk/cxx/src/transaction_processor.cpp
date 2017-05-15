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

#include <log4cxx/logger.h>
#include <zmqpp/zmqpp.hpp>

#include "proto/processor.pb.h"
#include "proto/transaction.pb.h"


#include "sawtooth/transaction_processor.h"

namespace sawtooth {

static log4cxx::LoggerPtr logger(log4cxx::Logger::getLogger
    ("sawtooth.TransactionProcessor"));

TransactionProcessor::TransactionProcessor(
        const std::string& connection_string):
        connection_string(connection_string), run(true) {
}

TransactionProcessor::~TransactionProcessor() {}

void TransactionProcessor::RegisterHandler(TransactionHandlerUPtr handler) {
    LOG4CXX_DEBUG(logger, "TransactionProcessor::RegisterHandler");

    TransactionHandlerPtr sptr(std::move(handler));
    std::string name = sptr->transaction_family_name();
    this->handlers[name] = sptr;
}

void TransactionProcessor::Register() {
    for (auto handler : this->handlers) {
        LOG4CXX_DEBUG(logger, "TransactionProcessor::Register: "
            << handler.first);
        auto versions = handler.second->versions();
        auto encodings = handler.second->encodings();

        for (auto version : versions) {
            for (auto encoding : encodings) {
                LOG4CXX_DEBUG(logger, "Register Handler: "
                    << handler.second->transaction_family_name()
                    << "Version: "<< version
                    << "Encoding: " << encoding);
                TpRegisterRequest request;
                request.set_family(handler.second->transaction_family_name());
                request.set_encoding(encoding);
                request.set_version(version);
                for (auto namesp : handler.second->namespaces()) {
                    request.add_namespaces(namesp);
                }
                FutureMessagePtr future = this->response_stream->SendMessage(
                        Message_MessageType_TP_REGISTER_REQUEST, request);
                TpRegisterResponse response;
                future->GetMessage(
                    Message_MessageType_TP_REGISTER_RESPONSE,
                    &response);
                if (response.status() != TpRegisterResponse::OK) {
                    LOG4CXX_ERROR(logger, "Register failed, status code: "
                        << response.status());
                    throw std::runtime_error("Registation failed");
                }
            }
        }
    }
}

void TransactionProcessor::HandleProcessingRequest(const void* msg,
    size_t msg_size) {
    TpProcessRequest request;
    TpProcessResponse response;
    try {
        request.ParseFromArray(msg, msg_size);

        StringPtr header_data(request.release_header());
        StringPtr payload_data(request.release_payload());
        StringPtr signature_data(request.release_signature());

        TransactionUPtr txn(new Transaction( header_data,
            payload_data,
            signature_data));
        const TransactionHeader& txn_header = txn->header();
        const std::string& family = txn_header.family_name();
        auto iter = this->handlers.find(family);
        if (iter != this->handlers.end()) {
            // TBD match version and encoding
            try {
                GlobalStateUPtr global_state(
                    new GlobalState(
                        this->message_disptcher.CreateStream(),
                        request.context_id()));

                TransactionApplicatorUPtr applicator = iter->second->GetApplicator(
                        std::move(txn),
                        std::move(global_state));
                try {
                    applicator->Apply();
                    response.set_status(TpProcessResponse::OK);
                } catch (std::exception& e ) {
                    LOG4CXX_ERROR(logger, "applicator->Apply error"
                                << e.what());
                    response.set_status(TpProcessResponse::INTERNAL_ERROR);
                } catch(...) {
                    LOG4CXX_ERROR(logger, "applicator->Apply unknown error");
                    response.set_status(
                        TpProcessResponse::INVALID_TRANSACTION);
                }
            } catch (std::exception& e) {
                response.set_status(
                        TpProcessResponse::INTERNAL_ERROR);
                LOG4CXX_ERROR(logger, "TransactionProcessor -> Appl error"
                    << e.what());
                throw;
            }
        } else {
            // no handler -- not sure if this is the right answer?
            response.set_status(TpProcessResponse::INVALID_TRANSACTION);
        }
    } catch (std::exception& e ) {
        LOG4CXX_ERROR(logger, "TransactionProcessor -> Appl error"
                    << e.what());
        response.set_status(TpProcessResponse::INTERNAL_ERROR);
    } catch (...) {
        LOG4CXX_ERROR(logger, "TransactionProcessor -> Appl error unknown");
        response.set_status(TpProcessResponse::INTERNAL_ERROR);
    }
    this->response_stream->SendMessage(
        Message_MessageType_TP_PROCESS_RESPONSE, response);
}

void TransactionProcessor::Run() {
    try {
        this->message_disptcher.Connect(this->connection_string);
        this->response_stream = this->message_disptcher.CreateStream();

        this->Register();

        zmqpp::socket socket(this->message_disptcher.context(), zmqpp::socket_type::dealer);
        socket.connect("inproc://request_queue");

        while (this->run) {
            zmqpp::message zmsg;
            socket.receive(zmsg);
            this->HandleProcessingRequest(zmsg.raw_data(0), zmsg.size(0));
        }
    } catch(std::exception& e) {
        LOG4CXX_ERROR(logger, "TransactionProcessor::Run ERROR: " << e.what());
    }
}

}  // namespace sawtooth


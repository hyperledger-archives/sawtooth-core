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

#include "sawtooth/exceptions.h"
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

        for (auto version : versions) {
            LOG4CXX_DEBUG(logger, "Register Handler: "
                << handler.second->transaction_family_name()
                << " Version: " << version);
            TpRegisterRequest request;
            request.set_family(handler.second->transaction_family_name());
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

void TransactionProcessor::HandleProcessingRequest(const void* msg,
        size_t msg_size,
        const std::string& correlation_id) {
    TpProcessRequest request;
    TpProcessResponse response;
    try {
        request.ParseFromArray(msg, msg_size);

        TransactionHeader* txn_header(request.release_header());

        StringPtr payload_data(request.release_payload());
        StringPtr signature_data(request.release_signature());

        TransactionUPtr txn(new Transaction( txn_header,
            payload_data,
            signature_data));

        const std::string& family = txn_header->family_name();

        auto iter = this->handlers.find(family);
        if (iter != this->handlers.end()) {
            // TBD match version
            try {
                GlobalStateUPtr global_state(
                    new GlobalState(
                        this->message_dispatcher.CreateStream(),
                        request.context_id()));

                TransactionApplicatorUPtr applicator = iter->second->GetApplicator(
                        std::move(txn),
                        std::move(global_state));
                try {
                    applicator->Apply();
                    response.set_status(TpProcessResponse::OK);
                } catch (sawtooth::InvalidTransaction& e ) {
                    LOG4CXX_ERROR(logger, "applicator->Apply error"
                                << e.what());
                    response.set_status(
                        TpProcessResponse::INVALID_TRANSACTION);
                } catch(...) {
                    LOG4CXX_ERROR(logger, "applicator->Apply unknown error");
                    response.set_status(
                        TpProcessResponse::INTERNAL_ERROR);
                }
            } catch (std::exception& e) {
                response.set_status(
                        TpProcessResponse::INTERNAL_ERROR);
                LOG4CXX_ERROR(logger, "TransactionProcessor -> Apply error"
                    << e.what());
                throw;
            }
        } else {
            // no handler -- not sure if this is the right answer?
            response.set_status(TpProcessResponse::INVALID_TRANSACTION);
        }
    } catch (std::exception& e ) {
        LOG4CXX_ERROR(logger, "TransactionProcessor -> Apply error"
                    << e.what());
        response.set_status(TpProcessResponse::INTERNAL_ERROR);
    } catch (...) {
        LOG4CXX_ERROR(logger, "TransactionProcessor -> Apply error unknown");
        response.set_status(TpProcessResponse::INTERNAL_ERROR);
    }
    this->response_stream->SendResponseMessage(
        Message_MessageType_TP_PROCESS_RESPONSE, response, correlation_id);
}

void TransactionProcessor::Run() {
    try {
        this->response_stream = this->message_dispatcher.CreateStream();
        zmqpp::socket socket(this->message_dispatcher.context(), zmqpp::socket_type::dealer);
        LOG4CXX_DEBUG(
            logger,
            "Connect to inproc://request_queue");
        socket.connect("inproc://request_queue");

        // Note that we are requesting a connect to the validator, but when this
        // returns it does not mean that we are actually connected.  We need to
        // wait for an event from the message dispatcher.
        LOG4CXX_INFO(
            logger,
            "Connect to: " << this->connection_string);
        this->message_dispatcher.Connect(this->connection_string);

        bool server_is_connected = false;

        while (this->run) {
            zmqpp::message zmsg;
            socket.receive(zmsg);

            Message validator_message;
            validator_message.ParseFromArray(zmsg.raw_data(0), zmsg.size(0));
            switch (validator_message.message_type()) {
                case Message::TP_PROCESS_REQUEST: {
                    this->HandleProcessingRequest(
                        validator_message.content().data(),
                        validator_message.content().length(),
                        validator_message.correlation_id());
                    break;
                }
                case MessageDispatcher::SERVER_CONNECT_EVENT: {
                    // If we are not already connected, we need to register
                    if (!server_is_connected) {
                        LOG4CXX_INFO(
                            logger,
                            "TransactionProcessor::Run : Server connected");
                            this->Register();
                    }

                    server_is_connected = true;
                    break;
                }
                case MessageDispatcher::SERVER_DISCONNECT_EVENT: {
                    LOG4CXX_INFO(
                        logger,
                        "TransactionProcessor::Run : Server disconnected");
                    server_is_connected = false;
                    break;
                }
                default: {
                    LOG4CXX_ERROR(
                        logger,
                        "TransactionProcessor::Run : Unknown message type: "
                           << validator_message.message_type());
                    break;
                }
            }
        }

        LOG4CXX_INFO(
            logger,
            "Close message dispatcher");
        this->message_dispatcher.Close();
    } catch(std::exception& e) {
        LOG4CXX_ERROR(logger, "TransactionProcessor::Run ERROR: " << e.what());
    }
}

}  // namespace sawtooth

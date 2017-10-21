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
#include <sstream>

#include <log4cxx/logger.h>
#include <zmqpp/context.hpp>
#include <zmqpp/poller.hpp>
#include <zmqpp/socket.hpp>
#include <zmqpp/socket_types.hpp>
#include <zmqpp/socket_options.hpp>
#include <zmq.h>

#include "proto/processor.pb.h"
#include "proto/network.pb.h"

#include "sawtooth/message_dispatcher.h"


namespace sawtooth {

const std::string MessageDispatcher::DISPATCH_THREAD_ENDPOINT(
    "inproc://dispatch_thread");
const std::string MessageDispatcher::SERVER_MONITOR_ENDPOINT(
    "inproc://server_monitor");

const std::string MessageDispatcher::THREAD_READY_MESSAGE("READY");
const std::string MessageDispatcher::THREAD_EXIT_MESSAGE("EXIT");

static log4cxx::LoggerPtr logger(log4cxx::Logger::getLogger
    ("sawtooth.MessageDispatcher"));

MessageDispatcher::MessageDispatcher():
        context_(),
        server_socket(this->context_, zmqpp::socket_type::dealer),
        message_socket(this->context_, zmqpp::socket_type::dealer),
        processing_request_socket(this->context_, zmqpp::socket_type::dealer),
        dispatch_thread_socket(this->context_, zmqpp::socket_type::pair),
        server_monitor_socket(this->context_, zmqpp::socket_type::pair),
        server_is_connected(false) {
    this->message_socket.bind("inproc://send_queue");
    this->processing_request_socket.bind("inproc://request_queue");
    this->dispatch_thread_socket.bind(MessageDispatcher::DISPATCH_THREAD_ENDPOINT);

    // Start monitoring the server socket for the connect and disconnect events.
    //
    // In reality, what we would really like is to monitor at this time for
    // connect and then when the state changes to connected, monitor solely for
    // the disconnect event and vice versa.  That way we poll in the most
    // efficient way as once we are in the disconnected state, the monitor will
    // keep giving is disconnect events if we are monitoring them.  However,
    // the problem seems to be that once we start monitoring, we are not allowed
    // to change what we are monitoring for.  Would love if someone could solve
    // this problem.
    if (zmq_socket_monitor(
            this->server_socket,
            MessageDispatcher::SERVER_MONITOR_ENDPOINT.c_str(),
            ZMQ_EVENT_CONNECTED | ZMQ_EVENT_DISCONNECTED)) {
        LOG4CXX_ERROR(
            logger,
            "Error trying to monitor server socket: "
                << zmq_errno());
        throw std::runtime_error("Failed to monitor server socket events");
    }
    // Connect socket to the monitor
    this->server_monitor_socket.connect(
        MessageDispatcher::SERVER_MONITOR_ENDPOINT);

    // Start the thread to process incoming messages, and then wait for the
    // thread to indicate it is ready
    this->dispatch_thread = std::thread(
        [this] {
            this->DispatchThread();
        });
    std::string throw_away_message;
    do {
        this->dispatch_thread_socket.receive(throw_away_message);
    } while(throw_away_message != MessageDispatcher::THREAD_READY_MESSAGE);
}

MessageDispatcher::~MessageDispatcher() {
    // Signal the dispatch thread to stop and join.
    this->dispatch_thread_socket.send(
        MessageDispatcher::THREAD_EXIT_MESSAGE, true);
    this->dispatch_thread.join();
}

// Connect to the validator component endpoint socket
void MessageDispatcher::Connect(const std::string& connection_string) {
    LOG4CXX_INFO(logger, "Connecting to " << connection_string);

    // It is worth noting that the connect message returning successfully does
    // not actually indicate that the connection has completed.  Per the ZMQ
    // documentation:
    //
    // "...for most transports and socket types the connection is not performed
    // immediately but as needed by ØMQ. Thus a successful call to zmq_connect()
    // does not mean that the connection was or could actually be established."
    //
    // Therefore, we will perform the connection and we will simply monitor, in
    // the dispatch thread, the server socket to detect the connected event
    // and from that we can let the transaction processor know.
    try {
        this->server_socket.connect(connection_string.c_str());
    } catch(std::exception& e) {
        LOG4CXX_ERROR(logger, "Connection to validator failed: " << e.what());
        throw;
    }
}

void MessageDispatcher::Close() {
    LOG4CXX_INFO(logger, "Disconnect server socket");
    std::string last_endpoint =
        this->server_socket.get<std::string>(
            zmqpp::socket_option::last_endpoint);
    this->server_socket.disconnect(last_endpoint);
}

void MessageDispatcher::ReceiveMessage() {
    zmqpp::message zmsg;
    this->server_socket.receive(zmsg);

    MessageUPtr msg_proto(new Message());
    msg_proto->ParseFromArray(zmsg.raw_data(0), zmsg.size(0));

    LOG4CXX_DEBUG(logger, "ReceiveMessage MessageType: "
        << msg_proto->message_type());

    switch (msg_proto->message_type()) {
        case Message_MessageType_TP_PROCESS_REQUEST: {
            this->processing_request_socket.send(zmsg);
            break;
        }
        case Message_MessageType_PING_REQUEST: {
            LOG4CXX_DEBUG(
                logger,
                "Received PING_REQUEST with correlation_id: "
                    << msg_proto->correlation_id());

            // Create a ping response message, set the status to OK, and
            // serialize it.
            PingResponse response;

            std::stringstream proto_stream;
            response.SerializeToOstream(&proto_stream);

            // Encapsulate the protobuf ping response in a message and
            // serialize it as well.
            Message msg;
            std::string msg_data;
            msg.set_message_type(Message_MessageType_PING_RESPONSE);
            msg.set_correlation_id(msg_proto->correlation_id());
            msg.set_content(proto_stream.str());
            msg.SerializeToString(&msg_data);

            // Encapsulate the message in a ZMQ message and send to the
            // validator
            zmqpp::message message;
            message.add(msg_data.data(), msg_data.length());
            this->server_socket.send(message);

            break;
        }
        default: {
            std::unique_lock<std::mutex> lock(this->mutex);
            const std::string& correlation_id = msg_proto->correlation_id();
            auto iter = this->message_futures.find(correlation_id);
            if (iter != this->message_futures.end()) {
                iter->second->SetMessage(std::move(msg_proto));
                this->message_futures.erase(iter);
            } else {
                LOG4CXX_DEBUG(logger, "Received Message without matching "
                    << "correlation_id:" << correlation_id);
            }
        }
    }
}

void MessageDispatcher::SendMessage() {
    zmqpp::message message;
    this->message_socket.receive(message);
    this->server_socket.send(message);
}

void MessageDispatcher::HandleConnectionChange(){
    // Get the next event for the server socket
    uint16_t event = this->GetServerSocketEvent(this->server_monitor_socket);

    // If we are not connected to the server and the event was a
    // connected event or we are connected and the event was a
    // disconnected event, we need to let the transaction processor
    // know so that it can perform the proper action.
    if ((server_is_connected && (ZMQ_EVENT_DISCONNECTED & event)) ||
        (!server_is_connected && (ZMQ_EVENT_CONNECTED & event))) {
        // Set the server connection state appropriately
        server_is_connected = ZMQ_EVENT_CONNECTED == event;
        LOG4CXX_INFO(
            logger,
            "Server connection state changed to: "
                << (server_is_connected ? "CONNECTED" : "DISCONNECTED"));

        // Create a new message for the transaction processor and set
        // its type to an appropriate event type value and queue up the
        // message in the transaction processors queue.
        Message msg;
        msg.set_message_type(
            ZMQ_EVENT_CONNECTED == event ?
                SERVER_CONNECT_EVENT : SERVER_DISCONNECT_EVENT);

        std::string msg_data;
        msg.SerializeToString(&msg_data);

        zmqpp::message zmsg;
        zmsg.add(msg_data.data(), msg_data.length());
        this->processing_request_socket.send(zmsg);
    }
}

uint16_t MessageDispatcher::GetServerSocketEvent(
    zmqpp::socket& server_monitor_socket
    ) {
    // First part of the message contains event number/type and value.  We only
    // care about the event type.
    zmqpp::message event;
    server_monitor_socket.receive(event);

    // Note - don't be tempted to use the get() method or the stream extraction
    // operator (>>) as they _seem_ (I say seem because I haven't looked at the
    // source code) to assume that the 16-bit integer has been transmitted in
    // big endian, but it appears that the server monitor socket data is simply
    // in processor native format.
    return *reinterpret_cast<const uint16_t *>(event.raw_data());
}

MessageStreamPtr MessageDispatcher::CreateStream() {
    return std::shared_ptr<MessageStream>(new MessageStream(&this->context_,
        this->message_futures, this->mutex));
}

void MessageDispatcher::DispatchThread() {
    zmqpp::poller socket_poller;
    socket_poller.add(this->server_socket);
    socket_poller.add(this->message_socket);
    socket_poller.add(this->server_monitor_socket);

    // Create a socket for inter-thread communication, connect with the other
    // side, let message dispatcher know that we are ready, then add the
    // socket to our poller
    zmqpp::socket dispatch_socket(this->context_, zmqpp::socket_type::pair);
    dispatch_socket.connect(MessageDispatcher::DISPATCH_THREAD_ENDPOINT);
    dispatch_socket.send(std::string(MessageDispatcher::THREAD_READY_MESSAGE));
    socket_poller.add(dispatch_socket);

    bool threadShouldExit = false;

    while (!threadShouldExit) {
        socket_poller.poll();
        if (socket_poller.has_input(this->server_socket)) {
            this->ReceiveMessage();
        }
        if (socket_poller.has_input(this->message_socket)) {
            this->SendMessage();
        }
        if (socket_poller.has_input(server_monitor_socket)) {
            this->HandleConnectionChange();
        }
        if (socket_poller.has_input(dispatch_socket)) {
            std::string message;
            dispatch_socket.receive(message);
            threadShouldExit = (message == MessageDispatcher::THREAD_EXIT_MESSAGE);
        }
    }

    // Stop monitoring the server socket.  The documentation doesn't mention
    // this, but it appears that passing NULL for the endpoint causes the
    // monitoring to stop.
    this->server_monitor_socket.disconnect(
        MessageDispatcher::SERVER_MONITOR_ENDPOINT);
    zmq_socket_monitor(this->server_socket, nullptr, ZMQ_EVENT_ALL);
}

}  // namespace sawtooth

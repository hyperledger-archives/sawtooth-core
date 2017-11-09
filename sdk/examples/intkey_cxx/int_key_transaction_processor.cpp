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
#include <iostream>
#include <string>

#include "log4cxx/logger.h"
#include "log4cxx/basicconfigurator.h"

#include "sawtooth/address_mapper.h"
#include "sawtooth/transaction_processor.h"
#include "sawtooth/exceptions.h"

#include "json.hpp"

using namespace log4cxx;

using namespace nlohmann;

static log4cxx::LoggerPtr logger(log4cxx::Logger::getLogger
    ("sawtooth.IntKeyCXX"));

static const std::string INTKEY_NAMESPACE = "intkey";


// utility function to provide copy conversion from vector of bytes
// to a stl string container.
std::string ToString(const std::vector<std::uint8_t>& in) {
    const char* data = reinterpret_cast<const char*>(&(in[0]));
    std::string out(data, data+in.size());
    return out;
}

// utility function to provide copy conversion from stl string container
// to a vector of bytes.
std::vector<std::uint8_t> ToVector(const std::string& in) {
    std::vector<std::uint8_t> out(in.begin(), in.end());
    return out;
}

// Handles the processing of a IntKey transactions.
class IntKeyApplicator:  public sawtooth::TransactionApplicator {
 public:
    IntKeyApplicator(sawtooth::TransactionUPtr txn,
        sawtooth::GlobalStateUPtr state) :
        TransactionApplicator(std::move(txn), std::move(state)),
            address_mapper(INTKEY_NAMESPACE) { }

    void Apply() {
        LOG4CXX_DEBUG(logger, "IntKeyApplicator::Apply");

        const std::string& raw_data = this->txn->payload();
        std::vector<uint8_t> data_vector = ToVector(raw_data);
        json intkey_cmd = json::from_cbor(data_vector);

        if (!intkey_cmd.is_object()) {
            throw sawtooth::InvalidTransaction(
                "CBOR Object as the encoded command");
        }
        auto verb_it = intkey_cmd.find("Verb");
        if (verb_it == intkey_cmd.end()) {
            throw sawtooth::InvalidTransaction(
                "Verb is required");
        }
        std::string verb = *verb_it;

        auto name_it = intkey_cmd.find("Name");
        if (name_it == intkey_cmd.end()) {
            throw sawtooth::InvalidTransaction(
                "Name is required");
        }
        std::string name = *name_it;
        if (name.length() == 0 || name.length() > 20) {
            throw sawtooth::InvalidTransaction(
                "Name is invalid, name must be between" \
                " 1 and 20 characters in length");
        }

        auto value_it = intkey_cmd.find("Value");
        if (value_it == intkey_cmd.end()) {
            throw sawtooth::InvalidTransaction(
                "Value is required");
        }
        int value = (*value_it).get<int>();

        if (verb == "set") {
            this->DoSet(name, value);
        } else if (verb == "inc") {
            this->DoInc(name, value);
        } else if (verb == "dec") {
            this->DoDec(name, value);
        } else {
            std::stringstream error;
            error << "invalid Verb: '" << verb << "'";
            throw sawtooth::InvalidTransaction(
                error.str());
        }
    }

 private:
    sawtooth::AddressMapper address_mapper;

 private:
    std::string MakeAddress(const std::string& name) {
        return this->address_mapper.MakeAddress(name);
    }

    // Handle an IntKey 'set' verb action. This sets a IntKey value to
    // the given value.
    void DoSet(const std::string& name, int value) {
        auto address = this->MakeAddress(name);
        LOG4CXX_DEBUG(logger, "IntKeyApplicator::DoSet Name: " << name
            << " Value: " << value << " Address: " << address);

        std::string state_value_rep;
        json state_value_map;
        if(this->state->GetState(&state_value_rep, address)) {
            if (state_value_rep.length() != 0) { // empty rep
                std::vector<std::uint8_t> state_value_rep_v = ToVector(state_value_rep);
                state_value_map = json::from_cbor(state_value_rep_v);
                if (state_value_map.find(name) != state_value_map.end()) {
                    std::stringstream error;
                    error << "Verb was 'Set', but already exists: " <<
                            "Name: " << name << ", Value " <<
                            state_value_map[name];
                    throw sawtooth::InvalidTransaction(error.str());
                }
            }
        }

        state_value_map[name] = value;

        // encode the value map back to cbor for storage.
        std::vector<std::uint8_t> state_value_rep_vec = json::to_cbor(state_value_map);
        state_value_rep = ToString(state_value_rep_vec);
        this->state->SetState(address, state_value_rep);
    }

    // Handle an IntKey 'inc' verb action. This increments an IntKey value
    // stored in global state by a given value.
    void DoInc(const std::string& name, int value) {
        auto address = this->MakeAddress(name);
        LOG4CXX_DEBUG(logger, "IntKeyApplicator::DoInc Name: " << name
            << " Value: " << value << " Address: " << address);

        json state_value_map;
        std::string state_value_rep;
        if(this->state->GetState(&state_value_rep, address)) {
            std::vector<std::uint8_t> state_value_rep_v = ToVector(state_value_rep);
            
            state_value_map = json::from_cbor(state_value_rep_v);
            if (state_value_map.find(name) == state_value_map.end()) {
                std::stringstream error;
                error << "Verb was 'Inc', but value does not exist for " <<
                        "Name: " << name;
                throw sawtooth::InvalidTransaction(error.str());
            }
            LOG4CXX_DEBUG(logger, "found");
        } else {
            std::stringstream error;
            error << "Verb was 'inc', but address not found in state for " <<
                "Name: " << name;
            throw sawtooth::InvalidTransaction(error.str());
        }
        LOG4CXX_DEBUG(logger, "address received: " << address << "="
            << state_value_map[name]);

        int state_value = state_value_map[name].get<int>();
        state_value += value;
        state_value_map[name] = state_value;

        std::vector<std::uint8_t> state_value_rep_vec =
            json::to_cbor(state_value_map);
        state_value_rep = ToString(state_value_rep_vec);
        this->state->SetState(address, state_value_rep);
    }

    // Handle an IntKey 'dec' verb action. This decrements an IntKey value
    // stored in global state by a given value.
    void DoDec(const std::string& name, int value) {
        auto address = this->MakeAddress(name);
        LOG4CXX_DEBUG(logger, "IntKeyApplicator::DoDec Name: " << name
            << " Value: " << value << " Address: " << address);

        json state_value_map;
        std::string state_value_rep;
        if(this->state->GetState(&state_value_rep, address)) {
            std::vector<std::uint8_t> state_value_rep_v = ToVector(state_value_rep);
            state_value_map = json::from_cbor(state_value_rep_v);

            if (state_value_map.find(name) == state_value_map.end()) {
                std::stringstream error;
                error << "Verb was 'dec', but value does not exist for " <<
                        "Name: " << name;
                throw sawtooth::InvalidTransaction(error.str());
            }
        } else {
            std::stringstream error;
            error << "Verb was 'dec', but address not found in state for " <<
                        "Name: " << name;
            throw sawtooth::InvalidTransaction(error.str());
        }
        LOG4CXX_DEBUG(logger, "address received: " << address << "=" <<
            state_value_map[name]);

        int state_value = state_value_map[name].get<int>();
        state_value -= value;
        state_value_map[name] = state_value;

        std::vector<std::uint8_t> state_value_rep_vec = json::to_cbor(state_value_map);
        state_value_rep = ToString(state_value_rep_vec);
        this->state->SetState(address, state_value_rep);
    }
};

// Defines the IntKey Handler to register with the transaction processor
// sets the versions and types of transactions that can be handled.
class IntKeyHandler: public sawtooth::TransactionHandler {
 public:
    std::string transaction_family_name() const {
        return std::string("intkey");
    }
    std::list<std::string> versions() const {
        return {"1.0"};
    }
    std::list<std::string> namespaces() const {
        sawtooth::AddressMapper addr(INTKEY_NAMESPACE);
        return { addr.GetNamespacePrefix() };
    }
    sawtooth::TransactionApplicatorUPtr GetApplicator(
        sawtooth::TransactionUPtr txn,
        sawtooth::GlobalStateUPtr state) {
        return sawtooth::TransactionApplicatorUPtr(
            new IntKeyApplicator(std::move(txn), std::move(state)));
    }
};


int main(int argc, char** argv) {
    try {
        std::string connectString = "tcp://127.0.0.1:4004";

        // Check if there is a command-line parameter.
        // currently we expect the command line arguement to be
        // a connection string.
        if (argc > 2) {
            throw std::runtime_error("");
        } else if (argc == 2) {
            connectString = argv[1];
        }

        // Set up a simple configuration that logs on the console.
        BasicConfigurator::configure();

        // Create a transaction processor and register our
        // handlers with it.
        sawtooth::TransactionProcessor processor(connectString);
        sawtooth::TransactionHandlerUPtr transaction_handler(
            new IntKeyHandler());
        processor.RegisterHandler(
            std::move(transaction_handler));

        LOG4CXX_DEBUG(logger, "Run");
        processor.Run();

        return 0;
    } catch(std::exception& e) {
        LOG4CXX_ERROR(logger, "Unexpected exception exiting: " << e.what());
        std::cerr << e.what() << std::endl;
    } catch(...) {
        LOG4CXX_ERROR(logger, "Unexpected exception exiting: unknown type");
        std::cerr << "Exiting do to uknown exception." << std::endl;
    }
    return -1;
}

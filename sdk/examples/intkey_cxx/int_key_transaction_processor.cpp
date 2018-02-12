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

#include <ctype.h>
#include <string.h>

#include <iostream>
#include <string>

#include "log4cxx/logger.h"
#include "log4cxx/basicconfigurator.h"
#include "log4cxx/level.h"

#include "sawtooth_sdk.h"
#include "exceptions.h"

#include "address_mapper.h"
#include "json.hpp"

#define URL_PREFIX       "tcp://"
#define URL_PREFIX_LEN   6
#define URL_DEFAULT      "tcp://127.0.0.1:4004"

#define MIN_VALUE        0x0
#define MAX_VALUE        0xffffffff

using namespace log4cxx;

using namespace nlohmann;

static log4cxx::LoggerPtr logger(log4cxx::Logger::getLogger
    ("sawtooth.IntKeyCXX"));

static const std::string INTKEY_NAMESPACE = "intkey";


// utility function to provide copy conversion from vector of bytes
// to an stl string container.
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

// Handles the processing of IntKey transactions.
class IntKeyApplicator:  public sawtooth::TransactionApplicator {
 public:
    IntKeyApplicator(sawtooth::TransactionUPtr txn,
        sawtooth::GlobalStateUPtr state) :
        TransactionApplicator(std::move(txn), std::move(state)),
            address_mapper(new AddressMapper(INTKEY_NAMESPACE)) { };


    void CborToParams(std::string& verb, std::string& name, uint32_t& value) {
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

        verb = *verb_it;

        auto name_it = intkey_cmd.find("Name");
        if (name_it == intkey_cmd.end()) {
            throw sawtooth::InvalidTransaction(
                "Name is required");
        }

        name = *name_it;

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

        value = (*value_it).get<uint32_t>();
        if(value < MIN_VALUE || value > MAX_VALUE){
            std::stringstream error;
            error << "Value (" << value << ") is out of range [" <<
                MIN_VALUE << ", " << MAX_VALUE << "]";
            throw sawtooth::InvalidTransaction(error.str());
        }
    };

    void Apply() {
        LOG4CXX_DEBUG(logger, "IntKeyApplicator::Apply");
        std::string verb;
        std::string name;
        uint32_t value;

        CborToParams(verb, name, value);

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
    AddressMapperUPtr address_mapper;

 private:
    std::string MakeAddress(const std::string& name) {
        return this->address_mapper->MakeAddress(name, 64, std::string::npos);
    }

    // Handle an IntKey 'set' verb action. This sets a IntKey value to
    // the given value.
    void DoSet(const std::string& name, int value) {
        auto address = this->MakeAddress(name);
        LOG4CXX_DEBUG(logger, "IntKeyApplicator::DoSet Name: " << name
            << " Value: " << value << " Address: " << address);

        // Value is range checked earlier during cbor deserialization
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

        uint32_t state_value = state_value_map[name].get<uint32_t>();
        uint32_t remaining = MAX_VALUE - state_value;
        if(value > remaining) {
            std::stringstream error;
            error << "Value (" << value << ") is too large to inc existing" <<
                " (" << state_value << ") Max: " << MAX_VALUE;
            throw sawtooth::InvalidTransaction(error.str());
        }

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

        uint32_t state_value = state_value_map[name].get<uint32_t>();
        uint32_t remaining = state_value - MIN_VALUE;
        if(value > remaining) {
            std::stringstream error;
            error << "Value (" << value << ") is too large to dec existing" <<
                " (" << state_value << ") Min: " << MIN_VALUE;
            throw sawtooth::InvalidTransaction(error.str());
        }
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
    IntKeyHandler() {
        AddressMapperUPtr addr(new AddressMapper(INTKEY_NAMESPACE));

        namespacePrefix = addr->GetNamespacePrefix();
    }

    std::string transaction_family_name() const {
        return std::string("intkey");
    }

    std::list<std::string> versions() const {
        return {"1.0"};
    }

    std::list<std::string> namespaces() const {
        return { namespacePrefix };
    }

    sawtooth::TransactionApplicatorUPtr GetApplicator(
        sawtooth::TransactionUPtr txn,
        sawtooth::GlobalStateUPtr state) {
        return sawtooth::TransactionApplicatorUPtr(
            new IntKeyApplicator(std::move(txn), std::move(state)));
    }
private:
    std::string namespacePrefix;
};


void Usage(bool bExit = false, int exitCode = 1) {
    std::cout << "Usage" << std::endl;
    std::cout << "intkey_cxx [options] [connet_string]" << std::endl;
    std::cout << "  -h, --help - print this message" << std::endl;
    
    std::cout <<
    "  -v, -vv, -vvv - detailed logging output, more letters v more details"
    << std::endl;
    
    std::cout <<
    "  connect_string - connect string to validator in format tcp://host:port"
    << std::endl;
    
    if (bExit) {
        exit(exitCode);
    }
}


bool TestConnectString(const char* str) {
    const char* ptr = str;

    if (strncmp(str, URL_PREFIX, URL_PREFIX_LEN)) {
        return false;
    }

    ptr = str + URL_PREFIX_LEN;

    if (!isdigit(*ptr)) {
        if (*ptr == ':' || (ptr = strchr(ptr, ':')) == NULL) {
            return false;
        }
        ptr++;
    }
    else {
        for (int i = 0; i < 4; i++) {
            if (!isdigit(*ptr)) {
                return false;
            }

            ptr++;
            if (isdigit(*ptr)) {
                ptr++;
                if (isdigit(*ptr)) {
                    ptr++;
                }
            }

            if (i < 3) {
                if (*ptr != '.') {
                    return false;
                }
            }
            else {
                if (*ptr != ':') {
                    return false;
                }
            }
            ptr++;
        }
    }

    for (int i = 0; i < 4; i++) {
        if (!isdigit(*ptr)) {
            if (i == 0) {
                return false;
            }
            break;
        }
        ptr++;
    }

    if (*ptr != 0) {
        return false;
    }

    return true;
}

void ParseArgs(int argc, char** argv, std::string& connectStr) {
    bool bLogLevelSet = false;

    for (int i = 1; i < argc; i++) {
        const char* arg = argv[i];
        if (!strcmp(arg, "-h") || !strcmp(arg, "--help")) {
            Usage(true, 0);
        }
        else
        if (!strcmp(arg, "-v")) {
            // logLevel = Level::WARN_INT;
            logger->setLevel(Level::getWarn());
            bLogLevelSet = true;
        }
        else
        if (!strcmp(arg, "-vv")) {
            // logLevel = Level::INFO_INT;
            logger->setLevel(Level::getInfo());
            bLogLevelSet = true;
        }
        else
        if (!strcmp(arg, "-vvv")) {
            // logLevel = Level::ALL_INT; //DEBUG_INT, TRACE_INT;
            logger->setLevel(Level::getAll());
            bLogLevelSet = true;
        }
        else
        if (i != (argc - 1)) {
            std::cout << "Invalid command line argument:" << arg << std::endl;
            Usage(true);
        }
        else
        if (!TestConnectString(arg)) {
            std::cout << "Connect string is not in format host:port - "
            << arg << std::endl;
            Usage(true);
        }
        else {
            connectStr = arg;
        }
    }

    if (!bLogLevelSet) {
        logger->setLevel(Level::getError());
    }
}

int main(int argc, char** argv) {
    try {
        std::string connectString = URL_DEFAULT;

        ParseArgs(argc, argv, connectString);

        // Set up a simple configuration that logs on the console.
        BasicConfigurator::configure();

        // Create a transaction processor and register our
        // handlers with it.
        sawtooth::TransactionProcessor* p =
        sawtooth::TransactionProcessor::Create(connectString);
        sawtooth::TransactionProcessorUPtr processor(p);
        
        sawtooth::TransactionHandlerUPtr transaction_handler(
            new IntKeyHandler());

        processor->RegisterHandler(
            std::move(transaction_handler));

        LOG4CXX_DEBUG(logger, "\nRun");

        processor->Run();

        return 0;
    } catch(std::exception& e) {
        LOG4CXX_ERROR(logger, "Unexpected exception exiting: " << e.what());
        std::cerr << e.what() << std::endl;
    } catch(...) {
        LOG4CXX_ERROR(logger, "Unexpected exception exiting: unknown type");
        std::cerr << "Exiting due to unknown exception." << std::endl;
    }
    return -1;
}

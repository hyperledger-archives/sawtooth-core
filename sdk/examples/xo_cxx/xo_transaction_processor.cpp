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

#define URL_PREFIX       "tcp://"
#define URL_PREFIX_LEN   6
#define URL_DEFAULT      "tcp://127.0.0.1:4004"

using namespace std;
using namespace log4cxx;
using namespace sawtooth;

static LoggerPtr logger(Logger::getLogger
    ("sawtooth.XoCXX"));

static const string XO_NAMESPACE = "xo";


// A helper function to split a string into substrings one by one 
int GetToken(const string& src, string& dst, size_t startPos, const char* delimeters = ",") {
    size_t length = src.length();
    size_t pos = startPos;

    if ((pos = src.find_first_of(delimeters, startPos)) != string::npos) {
        if (pos > startPos)
            dst.assign(src, startPos, pos - startPos);
        else
            dst = "";

        pos++;
    } else {
        dst.assign(src, startPos, pos - length);
        pos = string::npos;
    }

    if (pos != string::npos && pos >= length) {
        pos = string::npos;
    }

    return pos;
}


// This is a helper class holding state fields  
class XoState{
public:
    // Parse CSV input string
    void FromCsv(const string& csv) {
        string lastState;
        size_t pos = 0;

        LOG4CXX_DEBUG(logger, "XoState::FromCsv(): " << csv);

        GetToken(csv, lastState, 0, "|");

        if ((pos = GetToken(csv, name, pos)) != string::npos) {
            if ((pos = GetToken(csv, board, pos)) != string::npos) {
                if ((pos = GetToken(csv, gameStatus, pos)) != string::npos) {
                    if ((pos = GetToken(csv, player1, pos)) != string::npos) {
                        GetToken(csv, player2, pos);
                    }
                }
            }
        }

        Dump();
    };

    // Create CSV string from the current fields
    void ToCsv(string& dst) {
        stringstream s;
        s << name << ',' << board << "," << gameStatus
          << "," << player1 << "," << player2;

        dst = s.str();

        LOG4CXX_DEBUG(logger, "XoState::ToCsv() end: " << dst);
    };

    // process 'take' action and update the state
    void ProcessTake(int space, const string& player) {
        char ch = (gameStatus == "P1-NEXT") ? 'X' : 'O';

        LOG4CXX_DEBUG(logger, 
            "XoState::ProcessTake: " 
            << space << ", " << ch << ", " << player.substr(0, 6));

        board[space] = ch;

        if (ch == 'X' ) {
            if ( player1 == "") {
                player1 = player;
            }
        } else {
            if (player2 == "") {
                player2 = player;
            }
        }
        
        const char* ptr = board.c_str();
        if ( (ptr[0] == ch && ptr[1] == ch && ptr[2] == ch)
                    ||
             (ptr[3] == ch && ptr[4] == ch && ptr[5] == ch)
                    ||
             (ptr[6] == ch && ptr[7] == ch && ptr[8] == ch)
                    ||
             (ptr[0] == ch && ptr[3] == ch && ptr[6] == ch)
                    ||
             (ptr[1] == ch && ptr[4] == ch && ptr[7] == ch)
                    ||
             (ptr[2] == ch && ptr[5] == ch && ptr[8] == ch)
                    ||
             (ptr[0] == ch && ptr[4] == ch && ptr[8] == ch)
                    ||
             (ptr[2] == ch && ptr[4] == ch && ptr[6] == ch) ) {
            gameStatus = (ch == 'X') ? "P1-WIN" : "P2-WIN";
        } else if (board.find('-') == string::npos) {
            gameStatus = "TIE";
        } else {
            gameStatus = (ch == 'X') ? "P2-NEXT" : "P1-NEXT";
        }

        Dump();
    };

    // Initialize new state (e.g. on 'create')
    void InitNew(const string& _name) {
        player1 = "";
        player2 = "";
        board = "---------";
        gameStatus = "P1-NEXT";
        name = _name;
    };

    // sate field getters
    const string& GetPlayer1() { return player1; };
    const string& GetPlayer2() { return player2; };
    const string& GetBoard() { return board; };
    const string& GetGameStatus() { return gameStatus; };

    // debug dump of the state
    void Dump() {
        LOG4CXX_DEBUG(logger, "XoState dump:");
        LOG4CXX_DEBUG(logger, "board: '" << board << "'");
        LOG4CXX_DEBUG(logger, "GameStatus: '" << gameStatus << "'");
        LOG4CXX_DEBUG(logger, "player1: '" << player1 << "'");
        LOG4CXX_DEBUG(logger, "player2: '" << player2 << "'");
    };

private:
    AddressMapperUPtr address_mapper;

    string player1;
    string player2;
    string board;
    string gameStatus;
    string name;
};

// This is a helper class holding transaction input  
class XoTransactionPayload {
public:
    // construct a class instance from CSV input string   
    explicit XoTransactionPayload(const string& csv) {
        size_t pos = 0;

        bValid = false;
        space = -1;

        if ( (pos = GetToken(csv, name, pos)) != string::npos) {
            if ( (pos = GetToken(csv, action, pos)) != string::npos) {
                GetToken(csv, spaceStr, pos);

                if (spaceStr.length() == 1) {
                   char ch = spaceStr[0];
                   if (isdigit(ch) && ch != '0') {
                       space = ch - '0' - 1;
                   }
                }
            }
        }

        Dump();
    };


    // Validate transaction input considering input player and current state 
    void ValidateGameData(XoState& xoState, string& player) {
        LOG4CXX_DEBUG(logger, 
            "XoTransactionPayload::Validate() for player: '" 
            << player.substr(0, 6) << "'");

        bValid = false;

        if (action == "take") {
            if (xoState.GetBoard().empty()) {
                throw InvalidTransaction(
                    "Invalid action: this action requires an existing game.");
            }
        } else if (action == "create") {
            if (!xoState.GetBoard().empty()) {
                throw InvalidTransaction(
                    "Invalid Action: Game already exists.");
            }
    
            if (name.find('|') != string::npos) {
                throw InvalidTransaction(
                    "Invalid Action: Name cannot include '|' symbol.");
            }

            bValid = true;
            return;
        } else if (action == "delete") {
            bValid = true;
            return;
        } else {
            stringstream error;
            error << "Invalid Action: " << action;
            throw InvalidTransaction(error.str());
        }

        const string& player1 = xoState.GetPlayer1();
        const string& player2 = xoState.GetPlayer2();
        const string& gameStatus = xoState.GetGameStatus();
        const string& board = xoState.GetBoard();


        if ( gameStatus == "P1-WIN"
                ||
             gameStatus == "P2-WIN"
                ||
             gameStatus == "TIE") {
           throw InvalidTransaction("Invalid Action: Game has ended.");
        }

        if ((!player1.empty() && gameStatus == "P1-NEXT" && player1 != player)
                ||
            (!player2.empty() && gameStatus == "P2-NEXT" && player2 != player)) {
            stringstream error;
            error << "Not this player's turn: " << player;
            throw InvalidTransaction(error.str());
        }

        if (space < 0 || space > 8) {
            stringstream error;
            error << "Invalid Action: invalid space" << spaceStr;
            throw InvalidTransaction(error.str());
        }

        if ((int)board.length() <= space || board[space] != '-') {
            stringstream error;
            error << "Invalid Action: space already taken" << space;
            throw InvalidTransaction(error.str());
        }

        bValid = true;

        LOG4CXX_DEBUG(logger, "XoTransactionPayload::Validate() OK");
        Dump();
    };

    // transaction input field getters 
    const string& GetName() { return name; };
    int GetSpace() { return space; };
    const string& GetAction() { return action; };

    // debug dump of the transaction input
    void Dump() {
        LOG4CXX_DEBUG(logger, "XoTransactionPayload dump:");
        LOG4CXX_DEBUG(logger, "name: '" << name << "'");
        LOG4CXX_DEBUG(logger, "action: '" << action << "'");
        LOG4CXX_DEBUG(logger, "space: '" << space << "'");
        LOG4CXX_DEBUG(logger, "bValid: " << ((bValid) ? "true" : "false"));
    };

private:
    string name;
    string action;
    int space;
    bool bValid;

    string spaceStr;
};

// Finds a field of '%%%...' and replaces it with the input string 
// (as many as it can fit) and, if necessary, pads the rest with spaces
void FillInField(char* buf, const char* str, int len) {
    char* ptr = strchr(buf, '%');
    if (ptr != NULL) {
        for (int i = 0; ptr[i] == '%'; i++) {
            ptr[i] = (i < len) ? str[i] : ' ';
        }
    }
}

// Finds a field of '%%%...' and replaces it with the input string 
// (as many as it can fit) and, if necessary, pads the rest with spaces
void FillInFieldStr(char* buf, const string& str) {
    FillInField(buf, str.c_str(), str.length());
}

// Finds a field of '%...' and replaces it with the input char 
// and, if necessary, pads the rest with spaces
void FillInFieldChar(char* buf, char ch) {
    FillInField(buf, &ch, 1);
}

// Finds a field of '%...' and replaces it with the input int 
// and, if necessary, pads the rest with spaces
// int param should be in the range of 1 to 9 
void FillInFieldInt(char* buf, int x) {
    FillInFieldChar(buf, (x >= 0 && x < 9) ? ('0' + (char)x) : '?');
}

// Dispaly transaction results for tutorial usage 
void Display(XoState& state, XoTransactionPayload& payload, string& player) {
    static char fmt[] =
    "\n+++++++++++++++++++++"
    "\n+                   +"
    "\n+  Player '%%%%%%'  +"
    "\n+  Takes space %    +"
    "\n+                   +"
    "\n+     Game: %%%%%%% +"
    "\n+ Player 1: %%%%%%  +"
    "\n+ Player 2: %%%%%%  +"
    "\n+    State: %%%%%%% +"
    "\n+                   +"
    "\n+     % | % | %     +"
    "\n+    -----------    +"
    "\n+     % | % | %     +"
    "\n+    -----------    +"
    "\n+     % | % | %     +"
    "\n+                   +"
    "\n++++++++++++++++++++";
    
    if (payload.GetAction() == "create") {
        stringstream screate;
        screate << "\n"
            << "Player '" << player.substr(0, 6) << "' "
            << "created a game '" << payload.GetName() << "'\n"
            << "\n";

        LOG4CXX_DEBUG(logger, screate.str());
    } else if (payload.GetAction() == "delete") {
        stringstream s;
        s << "\n" << "Game '" << payload.GetName() << "' deleted\n\n";
        LOG4CXX_DEBUG(logger, s.str());
    } else if (payload.GetAction() == "take") {
        const string& board = state.GetBoard();
        char str[sizeof(fmt)];

        memcpy(str, fmt, sizeof(str));

        FillInFieldStr(str, player);
        FillInFieldInt(str, payload.GetSpace() + 1);
        FillInFieldStr(str, payload.GetName());
        FillInFieldStr(str, state.GetPlayer1());
        FillInFieldStr(str, state.GetPlayer2());
        FillInFieldStr(str, state.GetGameStatus());

        for (int i = 0; i < 9; i++) {
            FillInFieldChar(str, board[i]);
        }
        LOG4CXX_DEBUG(logger, str);
    }
}

// Handles the processing of XO transactions.
class XoApplicator:  public TransactionApplicator {
 public:
    XoApplicator(TransactionUPtr _txn, GlobalStateUPtr _state) :
        TransactionApplicator(std::move(_txn), std::move(_state)),
        address_mapper(new AddressMapper(XO_NAMESPACE)) { };

    void Apply() {
        LOG4CXX_DEBUG(logger, "Xo::Apply");
        XoTransactionPayload xoTransactionPayload(txn->payload());
        TransactionHeaderPtr header = txn->header();
        string player = header->GetValue(TransactionHeaderSignerPublicKey);

        bool bStateLoaded = LoadState(xoTransactionPayload.GetName());
        xoTransactionPayload.ValidateGameData(xoState, player);

        if (xoTransactionPayload.GetAction() == "create") {
            xoState.InitNew(xoTransactionPayload.GetName());
            SaveState(xoTransactionPayload.GetName());
        } else if (xoTransactionPayload.GetAction() == "delete") {
            if ( !bStateLoaded ) {
                throw InvalidTransaction(
                    "Invalid Action: Game must exist to delete");
            }

            auto address = this->MakeAddress(xoTransactionPayload.GetName());
            try{
                this->state->DeleteState(address);
            } catch (...) {
                throw InvalidTransaction(
                    "Invalid Action: Failed to Delete State");
            }
        } else if (xoTransactionPayload.GetAction() == "take") {
            xoState.ProcessTake(xoTransactionPayload.GetSpace(), player);

            SaveState(xoTransactionPayload.GetName());
        }
        
        // Log for tutorial usage
        Display(xoState, xoTransactionPayload, player);
    };


private:
    AddressMapperUPtr address_mapper;
    XoState xoState;

private:
    // make an address for the game name
    string MakeAddress(const string& name) {
        try{
            return this->address_mapper->MakeAddress(name, 0, 64);
        } catch (...) {
            throw InvalidTransaction(
                "Invalid Action: Failed to to make address");
        }
    };

    // load current state for the game name
    bool LoadState(const string& name) {
        bool ok = false;
        if ( !name.empty() ) {
            auto address = this->MakeAddress(name);
            string stateStr;

            try {
                this->state->GetState(&stateStr, address);
                ok = !stateStr.empty();
            } catch (...) {
                throw InvalidTransaction(
                    "Invalid Action: Failed to Load State");
            }

            if (ok) {
                xoState.FromCsv(stateStr);
            }
        }
        return ok;
    };

    // update current state for the game name
    void SaveState(const string& name) {
        auto address = this->MakeAddress(name);
        string stateStr;
        
        xoState.ToCsv(stateStr);
        
        try{
            this->state->SetState(address, stateStr);
        } catch (...) {
            throw InvalidTransaction(
                "Invalid Action: Failed to Save State");
        }
    };
};

// Defines the XO Handler to register with the transaction processor
// sets the versions and types of transactions that can be handled.
class XoHandler: public TransactionHandler {
public:
    XoHandler() {
        AddressMapperUPtr
            addr(new AddressMapper(XO_NAMESPACE));

        namespacePrefix = addr->GetNamespacePrefix();
    }

    string transaction_family_name() const{
        return string("xo");
    }

    list<string> versions() const {
        return {"1.0"};
    }

    list<string> namespaces() const{
        return { namespacePrefix };
    }

    TransactionApplicatorUPtr GetApplicator(
        TransactionUPtr txn,
        GlobalStateUPtr state) {
        return TransactionApplicatorUPtr(
            new XoApplicator(move(txn), move(state)));
    }
private:
    string namespacePrefix;
};

// print usage
void Usage(bool bExit = false, int exitCode = 1) {
    cout << "Usage" << endl;
    cout << "xo_tp_cxx [options] [connet_string]" << endl;
    cout << "  -h, --help - print this message" << endl;

    cout <<
    "  -v, -vv, -vvv - detailed logging output, more letters v more details"
    << endl;

    cout <<
    "  connect_string - connect string to validator in format tcp://host:port"
    << endl;

    if (bExit) {
        exit(exitCode);
    }
}

// verify that the connect string in format host:port 
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
    } else {
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
            } else {
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

// parse command line arguments
void ParseArgs(int argc, char** argv, string& connectStr) {
    bool bLogLevelSet = false;

    for (int i = 1; i < argc; i++) {
        const char* arg = argv[i];
        if (!strcmp(arg, "-h") || !strcmp(arg, "--help")) {
            Usage(true, 0);
        } else if (!strcmp(arg, "-v")) {
            logger->setLevel(Level::getWarn());
            bLogLevelSet = true;
        } else if (!strcmp(arg, "-vv")) {
            logger->setLevel(Level::getInfo());
            bLogLevelSet = true;
        } else if (!strcmp(arg, "-vvv")) {
            logger->setLevel(Level::getAll());
            bLogLevelSet = true;
        } else if (i != (argc - 1)) {
            cout << "Invalid command line argument:" << arg << endl;
            Usage(true);
        } else if (!TestConnectString(arg)) {
            cout << "Connect string is not in format host:port - "
            << arg << endl;
            Usage(true);
        } else {
            connectStr = arg;
        }
    }

    if (!bLogLevelSet) {
        logger->setLevel(Level::getError());
    }
}


int main(int argc, char** argv) {
    
    try {
        string connectString = URL_DEFAULT;

        ParseArgs(argc, argv, connectString);

        // Set up a simple configuration that logs on the console.
        BasicConfigurator::configure();

        // Create a transaction processor and register our
        // handlers with it.
        TransactionProcessorUPtr processor(
            TransactionProcessor::Create(connectString));
        
        TransactionHandlerUPtr transaction_handler(new XoHandler());

        processor->RegisterHandler(move(transaction_handler));

        LOG4CXX_DEBUG(logger, "\nRun");

        processor->Run();

        return 0;

    } catch(exception& e) {
        LOG4CXX_ERROR(logger, "Unexpected exception exiting: " << e.what());
        cerr << e.what() << endl;
    } catch(...) {
        LOG4CXX_ERROR(logger, "Unexpected exception exiting: unknown type");
        cerr << "Exiting due to uknown exception." << endl;
    }
    return -1;
}

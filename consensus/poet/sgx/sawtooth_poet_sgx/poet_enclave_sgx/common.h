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

#include <stdlib.h>
#include <string>

#include <cryptopp/cryptlib.h>
#include <cryptopp/eccrypto.h>
#include <cryptopp/asn.h>

#include "poet.h"

#define ENCODESIGNATURE 1

class MemoryError : public std::runtime_error {
public:
    MemoryError(const std::string& msg) : runtime_error(msg)
    {}
}; // class MemoryError
class IOError : public std::runtime_error {
public:
    IOError(const std::string& msg) : runtime_error(msg)
    {}
}; // class IOError
class RuntimeError : public std::runtime_error {
public:
    RuntimeError(const std::string& msg) : runtime_error(msg)
    {}
}; // class RuntimeError
class IndexError : public std::runtime_error {
public:
    IndexError(const std::string& msg) : runtime_error(msg)
    {}
}; // class IndexError
class TypeError : public std::runtime_error {
public:
    TypeError(const std::string& msg) : runtime_error(msg)
    {}
}; // class TypeError
class DivisionByZero : public std::runtime_error {
public:
    DivisionByZero(const std::string& msg) : runtime_error(msg)
    {}
}; // class DivisionByZero
class OverflowError : public std::runtime_error {
public:
    OverflowError(const std::string& msg) : runtime_error(msg)
    {}
}; // class OverflowError
class SyntaxError : public std::runtime_error {
public:
    SyntaxError(const std::string& msg) : runtime_error(msg)
    {}
}; // class SyntaxError
class ValueError : public std::runtime_error {
public:
    ValueError(const std::string& msg) : runtime_error(msg)
    {}
}; // class ValueError
class SystemError : public std::runtime_error {
public:
    SystemError(const std::string& msg) : runtime_error(msg)
    {}
}; // class SystemError
class SystemBusyError : public std::runtime_error {
public:
    SystemBusyError(const std::string& msg) : runtime_error(msg)
    {}
}; // class SystemBusyError
class UnknownError : public std::runtime_error {
public:
    UnknownError(const std::string& msg) : runtime_error(msg)
    {}
}; // class UnknownError

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
double CurrentTime();

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void PyLog(
    poet_log_level_t type,
    const char *msg
    );
void PyLogV(
    poet_log_level_t type,
    const char *msg,
    ...);

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void ThrowPoetError(
    poet_err_t ret
    );

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
std::string CreateIdentifier(
    const std::string& signature);

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
class StringBuffer {
public:
    StringBuffer(size_t size) : buffer(size)
    {
        this->length = buffer.size();
    }
    virtual ~StringBuffer() {}

    std::string str()
    {
        return std::string(&this->buffer[0]);
    }

    char* data()
    {
        return &this->buffer[0];
    }

    std::vector<char> buffer;
    size_t length;
}; // class StringBuffer

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void InitializeInternal();
void TerminateInternal();



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

#pragma once
#include <stdexcept>
#include <string>

#include "sgx_error.h"
#include "poet.h"

namespace sawtooth {
    namespace poet {

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class SgxError : public std::exception
        {
        public:
            explicit SgxError() : errorCode(SGX_SUCCESS) {}
            explicit SgxError(
                sgx_status_t inErrorCode
                ) :
                errorCode(inErrorCode) {}
            virtual ~SgxError() {}

            sgx_status_t error() { return errorCode; }

            virtual char const * what() const throw()
            {
                return "Sgx Call Failed.";
            }

        private:
            sgx_status_t errorCode;
        }; // class SgxError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class PoetError : public std::runtime_error
        {
        public:
            PoetError(
                poet_err_t in_error,
                const std::string& msg
                ) :
                _error_code(in_error),
                runtime_error(msg) {}
            virtual ~PoetError() throw() {}

            poet_err_t error_code()  { return _error_code; };
        private:
            poet_err_t _error_code;
        }; // class PoetError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class MemoryError : public PoetError
        {
        public:
            explicit MemoryError(
                const std::string& msg
                ) :
                PoetError(POET_ERR_MEMORY, msg) {}
        }; // class MemoryError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class IOError : public PoetError
        {
        public:
            explicit IOError(
                const std::string& msg
                ) :
                PoetError(POET_ERR_IO, msg) {}
        }; // class IOError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class RuntimeError : public PoetError
        {
        public:
            explicit RuntimeError(
                const std::string& msg
                ) :
                PoetError(POET_ERR_RUNTIME, msg) {}
        }; // class RuntimeError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class IndexError : public PoetError
        {
        public:
            explicit IndexError(
                const std::string& msg
                ) :
                PoetError(POET_ERR_INDEX, msg) {}
        }; // class IndexError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class DivisionByZero : public PoetError
        {
        public:
            explicit DivisionByZero(
                const std::string& msg
                ) : PoetError(POET_ERR_DIVIDE_BY_ZERO, msg) {}
        }; // class DivisionByZero

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class OverflowError : public PoetError
        {
        public:
            explicit OverflowError(
                const std::string& msg
                ) : PoetError(POET_ERR_OVERFLOW, msg) {}
        }; // class OverflowError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class ValueError : public PoetError
        {
        public:
            explicit ValueError(
                const std::string& msg
                ) : PoetError(POET_ERR_VALUE, msg) {}
        }; // class ValueError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class SystemError : public PoetError
        {
        public:
            explicit SystemError(
                const std::string& msg
                ) : PoetError(POET_ERR_SYSTEM, msg) {}
        }; // class SystemError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class SystemBusyError : public PoetError
        {
        public:
            explicit SystemBusyError(
                const std::string& msg
                ) : PoetError(POET_ERR_SYSTEM_BUSY, msg) {}
        }; // class SystemBusyError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        class UnknownError : public PoetError
        {
        public:
            explicit UnknownError(
                const std::string& msg
                ) : PoetError(POET_ERR_UNKNOWN, msg) {}
        }; // class UnknownError

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        // Error checking utilities.
        template<typename PointerType>
        inline void ThrowIfNull(
            const PointerType ptr,
            const char* msg = nullptr
            )
        {
            if (!ptr) {
                throw ValueError(msg ? msg : "Unexpected null parameter.");
            }
        } // ThrowIfNull

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        template <typename except>
        inline void ThrowIf(
            bool condition,
            const char* msg
            )
        {
            if (condition) {
                throw except(msg);
            }
        } // ThrowIf

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void ThrowSgxError(
            sgx_status_t ret,
            const char* msg = nullptr
            );

    } // namespace poet
} // namespace sawtooth

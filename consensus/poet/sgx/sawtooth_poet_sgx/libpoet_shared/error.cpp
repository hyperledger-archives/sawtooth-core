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

#include <stdint.h>
#include <stdio.h>

#include "error.h"
#include "sgx_support.h"
#include "c11_support.h"

namespace sawtooth {
    namespace poet {

        typedef struct _sgx_errlist_t {
            const sgx_status_t err;
            const char *msg;
            const char *sug; /* Suggestion */
        } sgx_errlist_t;

#define SGX_ERR_ITEM(x) { x, #x, nullptr }
        /* Error code returned by sgx_create_enclave */
        static const sgx_errlist_t sgx_errlist[] = {
            {
                SGX_ERROR_UNEXPECTED,
                "Unexpected error occurred.",
                nullptr
            },
            {
                SGX_ERROR_INVALID_PARAMETER,
                "Invalid parameter.",
                nullptr
            },
            {
                SGX_ERROR_OUT_OF_MEMORY,
                "Out of memory.",
                nullptr
            },
            {
                SGX_ERROR_INVALID_STATE,
                "SGX API is invoked in incorrect order or state",
                nullptr
            },
            SGX_ERR_ITEM(SGX_ERROR_HYPERV_ENABLED),
            SGX_ERR_ITEM(SGX_ERROR_FEATURE_NOT_SUPPORTED),
            SGX_ERR_ITEM(SGX_ERROR_INVALID_FUNCTION),
            SGX_ERR_ITEM(SGX_ERROR_OUT_OF_TCS),
            SGX_ERR_ITEM(SGX_ERROR_ENCLAVE_CRASHED),
            SGX_ERR_ITEM(SGX_ERROR_ECALL_NOT_ALLOWED),
            SGX_ERR_ITEM(SGX_ERROR_OCALL_NOT_ALLOWED),
            SGX_ERR_ITEM(SGX_ERROR_UNDEFINED_SYMBOL),
            {
                SGX_ERROR_ENCLAVE_LOST,
                "Power transition occurred.",
                "Please refer to the sample \"PowerTransition\" for details."
            },
            {
                SGX_ERROR_INVALID_ENCLAVE,
                "Invalid enclave image.",
                nullptr
            },
            {
                SGX_ERROR_INVALID_ENCLAVE_ID,
                "Invalid enclave identification.",
                nullptr
            },
            {
                SGX_ERROR_INVALID_SIGNATURE,
                "Invalid enclave signature.",
                nullptr
            },
            SGX_ERR_ITEM(SGX_ERROR_NDEBUG_ENCLAVE),
            {
                SGX_ERROR_OUT_OF_EPC,
                "Out of EPC memory.",
                nullptr
            },
            {
                SGX_ERROR_NO_DEVICE,
                "Invalid SGX device.",
                "Please make sure SGX module is enabled in the BIOS, and install SGX driver afterwards."
            },
            {
                SGX_ERROR_MEMORY_MAP_CONFLICT,
                "Memory map conflicted.",
                nullptr
            },
            {
                SGX_ERROR_INVALID_METADATA,
                "Invalid enclave metadata.",
                nullptr
            },
            {
                SGX_ERROR_DEVICE_BUSY,
                "SGX device was busy.",
                nullptr
            },
            {
                SGX_ERROR_INVALID_VERSION,
                "Enclave version was invalid.",
                nullptr
            },
            SGX_ERR_ITEM(SGX_ERROR_MODE_INCOMPATIBLE),
            {
                SGX_ERROR_INVALID_ATTRIBUTE,
                "Enclave was not authorized.",
                nullptr
            },
            {
                SGX_ERROR_ENCLAVE_FILE_ACCESS,
                "Can't open enclave file.",
                nullptr
            },
            SGX_ERR_ITEM(SGX_ERROR_INVALID_MISC),
            SGX_ERR_ITEM(SGX_ERROR_MAC_MISMATCH),
            SGX_ERR_ITEM(SGX_ERROR_INVALID_CPUSVN),
            SGX_ERR_ITEM(SGX_ERROR_INVALID_ISVSVN),
            SGX_ERR_ITEM(SGX_ERROR_INVALID_KEYNAME),
            SGX_ERR_ITEM(SGX_ERROR_SERVICE_UNAVAILABLE),
            SGX_ERR_ITEM(SGX_ERROR_SERVICE_TIMEOUT),
            SGX_ERR_ITEM(SGX_ERROR_AE_INVALID_EPIDBLOB),
            SGX_ERR_ITEM(SGX_ERROR_SERVICE_INVALID_PRIVILEGE),
            SGX_ERR_ITEM(SGX_ERROR_EPID_MEMBER_REVOKED),
            SGX_ERR_ITEM(SGX_ERROR_UPDATE_NEEDED),
            SGX_ERR_ITEM(SGX_ERROR_NETWORK_FAILURE),
            SGX_ERR_ITEM(SGX_ERROR_AE_SESSION_INVALID),
            SGX_ERR_ITEM(SGX_ERROR_BUSY),
            SGX_ERR_ITEM(SGX_ERROR_MC_NOT_FOUND),
            SGX_ERR_ITEM(SGX_ERROR_MC_NO_ACCESS_RIGHT),
            SGX_ERR_ITEM(SGX_ERROR_MC_USED_UP),
            SGX_ERR_ITEM(SGX_ERROR_MC_OVER_QUOTA),
            SGX_ERR_ITEM(SGX_ERROR_EFI_NOT_SUPPORTED),
            SGX_ERR_ITEM(SGX_ERROR_NO_PRIVILEGE),
        };

        void ThrowSgxError(
            sgx_status_t ret,
            const char* msg
            )
        {
            char buffer[256];
            if (!msg) {
                msg = "";
            }

            if (ret != SGX_SUCCESS) {
                static size_t count =
                    sizeof(sgx_errlist)/sizeof(sgx_errlist[0]);

                for (int idx = 0; idx < count; idx++) {
                    if (sgx_errlist[idx].err == ret) {
                        snprintf(
                            buffer,
                            sizeof(buffer),
                            "%s: SGX ERROR: %s",
                            msg,
                            sgx_errlist[idx].msg);

                        if(SGX_ERROR_BUSY == ret) {
                            throw SystemBusyError(buffer);
                        } else {
                            throw SystemError(buffer);
                        }
                    }
                }

                snprintf(
                    buffer,
                    sizeof(buffer),
                    "%s: UNKNOWN SGX ERROR: 0x%.8X",
                    msg,
                    ret);
                throw SystemError(buffer);
            }
        } // ThrowSgxError

    } // namespace poet
} // namespace sawtooth

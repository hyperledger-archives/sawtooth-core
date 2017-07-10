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

////////////////////////////////////////////////////////////////////////////////
//  Description: 
//    This header provides Win32 specific traits classes for use with the
//    AutoHandle class.  Additionally, it also provides typedefs to so that
//    code is a little cleaner as the long templatized version of the
//    AutoHandle class is not necessary.
//
////////////////////////////////////////////////////////////////////////////////

#pragma once

#include "auto_handle.h"
#include "sgx_tcrypto.h"

namespace Intel
{

// SGX SHA256 State handle specialization
// When using an SGX SHA256 state handle file handle, you must specify the
// second type to the AutoHandle template because the handle is really just a
// typedef for a opaque void pointer, and there are several other handles like
// that in SGX.  For example:
//
// AutoHandle<sgx_sha_state_handle_t, SgxSha256StateHandleTraits>

struct SgxSha256StateHandleTraits
{
    static sgx_sha_state_handle_t InvalidHandle()
    {
        return NULL;
    }
    
    static void Cleanup(sgx_sha_state_handle_t handle)
    {
        sgx_sha256_close(handle);
    }
};

// SGX CMAC128 State handle specialization
// When using an SGX CMAC128 state handle file handle, you must specify the
// second type to the AutoHandle template because the handle is really just a
// typedef for a opaque void pointer, and there are several other handles like
// that in SGX.  For example:
//
// AutoHandle<sgx_cmac_state_handle_t, SgxCmac128StateHandleTraits>

struct SgxCmac128StateHandleTraits
{
    static sgx_cmac_state_handle_t InvalidHandle()
    {
        return NULL;
    }
    
    static void Cleanup(sgx_cmac_state_handle_t handle)
    {
        sgx_cmac128_close(handle);
    }
};

// SGX ECC256 State handle specialization
// When using an SGX ECC256 state handle file handle, you must specify the
// second type to the AutoHandle template because the handle is really just a
// typedef for a opaque void pointer, and there are several other handles like
// that in SGX.  For example:
//
// AutoHandle<sgx_ecc_state_handle_t, SgxEcc256StateHandleTraits>

struct SgxEcc256StateHandleTraits
{
    static sgx_ecc_state_handle_t InvalidHandle()
    {
        return NULL;
    }
    
    static void Cleanup(sgx_ecc_state_handle_t handle)
    {
        sgx_ecc256_close_context(handle);
    }
};

// Typedefs for the SGX handle types.

typedef AutoHandle<sgx_sha_state_handle_t, SgxSha256StateHandleTraits>
    SgxSha256StateHandle;
typedef AutoHandle<sgx_cmac_state_handle_t, SgxCmac128StateHandleTraits>
    SgxCmac128StateHandle;
typedef AutoHandle<sgx_ecc_state_handle_t, SgxEcc256StateHandleTraits>
    SgxEcc256StateHandle;

} // namespace Intel

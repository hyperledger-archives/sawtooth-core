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

// There are some Windows SGX library features that do not exist in the Linux
// version, so we are going to add the missing stuff here to make the other
// code platform-independent.

#include "sgx_error.h"

typedef enum _sgx_device_status_t {
    SGX_ENABLED,
    SGX_DISABLED_REBOOT_REQUIRED,
    SGX_DISABLED_LEGACY_OS,
    SGX_DISABLED,
    SGX_DISABLED_SCI_AVAILABLE
} sgx_device_status_t;

#define sgx_enable_device(pStatus) (*pStatus = SGX_ENABLED , SGX_SUCCESS)

// Missing error codes
#define MISSING_SGX_CODE(value) static_cast<sgx_status_t>(SGX_MK_ERROR(value))

/* Win10 platform with Hyper-V enabled */
#define SGX_ERROR_HYPERV_ENABLED        MISSING_SGX_CODE(0x0007)
/* Feature is not supported on this platform */
#define SGX_ERROR_FEATURE_NOT_SUPPORTED MISSING_SGX_CODE(0x0008)
/* The OS doesn't support EFI */
#define SGX_ERROR_EFI_NOT_SUPPORTED     MISSING_SGX_CODE(0x5001)
/* Not enough privelige to perform the operation */
#define SGX_ERROR_NO_PRIVILEGE          MISSING_SGX_CODE(0x5002)


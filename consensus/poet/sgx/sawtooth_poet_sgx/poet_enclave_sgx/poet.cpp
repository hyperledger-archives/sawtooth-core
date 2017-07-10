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

#include "common.h"
#include "poet_enclave.h"
#include <iostream>
#include <vector>

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
bool _is_sgx_simulator()
{
    return 0 != Poet_IsSgxSimulator();
} // _is_sgx_simulator

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
Poet::Poet(
    const std::string& dataDirectory,
    const std::string& enclaveModulePath,
    const std::string& spid
    )
{
    PyLog(POET_LOG_INFO, "Initializing SGX Poet enclave");
    PyLogV(POET_LOG_DEBUG, "Data directory: %s", dataDirectory.c_str());
    PyLogV(POET_LOG_DEBUG, "Enclave path: %s", enclaveModulePath.c_str());
    PyLogV(POET_LOG_DEBUG, "SPID: %s", spid.c_str());

    poet_err_t ret = Poet_Initialize(
        dataDirectory.c_str(),
        enclaveModulePath.c_str(),
        spid.c_str(),
        PyLog
        );
    ThrowPoetError(ret);
    PyLog(POET_LOG_WARNING, "SGX PoET enclave initialized.");

    StringBuffer mrEnclaveBuffer(Poet_GetEnclaveMeasurementSize());
    StringBuffer basenameBuffer(Poet_GetEnclaveBasenameSize());
    StringBuffer pseManifestHashBuffer(Poet_GetEnclavePseManifestHashSize());

    ThrowPoetError(
        Poet_GetEnclaveCharacteristics(
            mrEnclaveBuffer.data(),
            mrEnclaveBuffer.length,
            basenameBuffer.data(),
            basenameBuffer.length,
            pseManifestHashBuffer.data(),
            pseManifestHashBuffer.length));

    this->mr_enclave = mrEnclaveBuffer.str();
    this->basename = basenameBuffer.str();
    this->pse_manifest_hash = pseManifestHashBuffer.str();
} // Poet::Poet

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
Poet::~Poet()
{
    try {
        Poet_Terminate();
        TerminateInternal();
    } catch (...) {
    }
} // Poet::~Poet

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
std::string Poet::get_epid_group()
{
    StringBuffer epidGroupBuffer(Poet_GetEpidGroupSize());
    ThrowPoetError(
        Poet_GetEpidGroup(
            epidGroupBuffer.data(),
            epidGroupBuffer.length));

    return std::string(epidGroupBuffer.str());
} // Poet::get_epid_group

// XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
void Poet::set_signature_revocation_list(
    const std::string& signature_revocation_list
    )
{
    ThrowPoetError(
        Poet_SetSignatureRevocationList(signature_revocation_list.c_str()));
} // Poet::set_signature_revocation_lists

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
#pragma once

#include <map>
#include <memory>
#include <list>
#include <string>

#include "sawtooth_sdk.h"
#include "proto/transaction.pb.h"

#include "sawtooth/global_state.h"

namespace sawtooth {

class TransactionHeaderImpl: public TransactionHeader {
public:
    TransactionHeaderImpl(::TransactionHeader* header): header_(header) {};
    virtual ~TransactionHeaderImpl() {
        if (header_ != NULL) {
            delete header_;
        }
    };

    virtual int GetCount(TransactionHeaderField field) {
        int count = 0;
        switch (field) {
            case TransactionHeaderStringDependencies:
                count = header_->dependencies_size();
                break;

            case TransactionHeaderInputs:
                count = header_->inputs_size();
                break;

            case TransactionHeaderOutputs:
                count = header_->outputs_size();
                break;

            case TransactionHeaderNonce:
            case TransactionHeaderFamilyName:
            case TransactionHeaderFamilyVersion:
            case TransactionHeaderPayloadSha512:
            case TransactionHeaderBatcherPublicKey:
            case TransactionHeaderSignerPublicKey:
                count = 1;
                break;

            default:
                count = 0;
                break;
        }

        return count;
    };

    virtual const ::std::string& GetValue(TransactionHeaderField field, int index) {
        int count = 0;

        switch (field) {
            case TransactionHeaderStringDependencies:
                return header_->dependencies(index);
                break;

            case TransactionHeaderInputs:
                return header_->inputs(index);
                break;

            case TransactionHeaderOutputs:
                return header_->outputs(index);
                break;

            case TransactionHeaderNonce:
                return header_->nonce();
                break;

            case TransactionHeaderFamilyName:
                return header_->family_name();
                break;

            case TransactionHeaderFamilyVersion:
                return header_->family_version();
                break;

            case TransactionHeaderPayloadSha512:
                return header_->payload_sha512();
                break;

            case TransactionHeaderBatcherPublicKey:
                return header_->batcher_public_key();
                break;

            case TransactionHeaderSignerPublicKey:
                return header_->signer_public_key();
                break;

            default:
                return dummy;
                break;
        }
        return dummy;
     };

private:
    ::TransactionHeader* header_; // pointer to protobuf generated object
    ::std::string dummy;
};



}  // namespace sawtooth

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

class TxHeaderWrapper: public TxHeaderIF
{
public:
    TxHeaderWrapper(TransactionHeader* header): header_(header) {};
    virtual ~TxHeaderWrapper()
    {
        if (header_ != NULL)
        {
            delete header_;
        }
    };

    virtual int GetCount(TxHeaderField field)
    {
        int count = 0;
        switch (field)
        {
            case TxHeaderStringDependencies:
                count = header_->dependencies_size();
                break;

            case TxHeaderInputs:
                count = header_->inputs_size();
                break;

            case TxHeaderOutputs:
                count = header_->outputs_size();
                break;

            case TxHeaderNonce:
            case TxHeaderFamilyName:
            case TxHeaderFamilyVersion:
            case TxHeaderPayloadSha512:
            case TxHeaderBatcherPublicKey:
            case TxHeaderSignerPublicKey:
                count = 1;
                break;

            default:
                count = 0;
                break;
        }

        return count;
    };

    virtual const ::std::string& GetValue(TxHeaderField field, int index)
     {
        int count = 0;

        switch (field)
        {
            case TxHeaderStringDependencies:
                return header_->dependencies(index);
                break;

            case TxHeaderInputs:
                return header_->inputs(index);
                break;

            case TxHeaderOutputs:
                return header_->outputs(index);
                break;

            case TxHeaderNonce:
                return header_->nonce();
                break;

            case TxHeaderFamilyName:
                return header_->family_name();
                break;

            case TxHeaderFamilyVersion:
                return header_->family_version();
                break;

            case TxHeaderPayloadSha512:
                return header_->payload_sha512();
                break;

            case TxHeaderBatcherPublicKey:
                return header_->batcher_public_key();
                break;

            case TxHeaderSignerPublicKey:
                return header_->signer_public_key();
                break;

            default:
                return dummy;
                break;
        }
        return dummy;
     };

private:
    TransactionHeader* header_;
    ::std::string dummy;
};



}  // namespace sawtooth

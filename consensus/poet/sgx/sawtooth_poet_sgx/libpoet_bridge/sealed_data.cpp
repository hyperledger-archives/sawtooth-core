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

#include <fstream>
#include "zero.h"

#include "sealed_data.h"

namespace sawtooth {
    namespace poet {

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void SealedData::Load(
            const std::string& fileName,
            size_t sealedLength
            )
        {
            this->fileName = fileName;
            std::ifstream stateFile(this->fileName, std::ios::binary);
            if(stateFile.good()) {
                this->data.clear();
                this->data.assign(
                    std::istreambuf_iterator<char>(stateFile), 
                    std::istreambuf_iterator<char>());
                stateFile.close();

                // if we have the wrong amount of data
                if (sealedLength != data.size()) {
                    // throw it away and start over
                    // in the future we will want a function 
                    // to convert the states if the versions
                    // change.
                    this->data.resize(sealedLength);
                    ZeroV(this->data);
                }
            } else {
                this->data.resize(sealedLength);
                ZeroV(this->data);
            }
        }// SealedData::Load

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void SealedData::Save()
        {
            std::ofstream output(this->fileName, std::ios::binary );

            std::copy( 
                this->data.begin(), 
                this->data.end(),
                std::ostreambuf_iterator<char>(output));
            output.close();
        } // SealedData::Save

        // XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
        void SealedData::Clear()
        {
            ZeroV(this->data);
            this->data.clear();
            remove(this->fileName.c_str());
        } // SealedData::Clear

    } // namespace poet
} // namespace sawtooth

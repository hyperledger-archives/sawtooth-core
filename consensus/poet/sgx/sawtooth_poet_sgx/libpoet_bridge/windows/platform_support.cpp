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

// This is Windows implementation backing the platform-independent services that
// are used by libpoet

#include <windows.h>
#include <shlobj.h>
#include "error.h"
#include "platform_support.h"

namespace sawtooth {
    namespace poet {
        const size_t MAXIMUM_PATH_LENGTH = MAX_PATH;
        const std::string PATH_SEPARATOR("\\");

        void Sleep(size_t milliseconds) {
            ::Sleep(static_cast<DWORD>(milliseconds));
        } // Sleep
    } // namespace poet
} // namespace sawtooth

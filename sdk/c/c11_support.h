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

#ifndef C11_SUPPORT_H
#define C11_SUPPORT_H

#include <stdlib.h>
// If the compiler has been built with optional extensions, then we can have
// some of the missing functions made available by defining the appropriate
// preprocessor define before including string.h
#ifdef __STDC_LIB_EXT1__
    #define __STDC_WANT_LIB_EXT1__ 1
#else
    int strncpy_s(char *dest, size_t sizeInBytes,
                     const char *src, size_t count);
#endif // #ifdef __STDC_LIB_EXT1__

#include <string.h>

#ifndef STRUNCATE
#define STRUNCATE 80
#endif

#endif

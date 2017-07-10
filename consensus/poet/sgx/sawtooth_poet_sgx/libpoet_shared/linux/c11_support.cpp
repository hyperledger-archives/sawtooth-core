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

#include <stdio.h>
#include <errno.h>
#include <string.h>
#include "c11_support.h"

#ifndef __STDC_LIB_EXT1__

int memset_s(void *dest, size_t max, int c, size_t count)
{
    // Figure out how many characters we are going to set (either the count or
    // the max) and only set that many.  Also, the real reason the memset_s is
    // being used is to prevent the zero-ing of a buffer that may contain
    // sensitive information from being optimized away.  Convert the pointer to
    // a volatile to try to prevent the compiler from doing this.
    memset(static_cast<void * volatile>(dest), c,  max < count ? max : count);

    // If we are able to set all of the bytes, then we return an error.
    return max < count ? EINVAL : 0;
}
#endif // #ifdef __STDC_LIB_EXT1__

int vsnprintf_s(
    char *buffer,
    size_t bufsz,
    const char* format,
    va_list arg)
{
    return vsnprintf(buffer, bufsz, format, arg);
} // vsnprintf_s

int vsnprintf_s(
    char* buffer,
    size_t bufsz,
    size_t count,
    const char* format,
    va_list arg)
{
    return vsnprintf_s(buffer, bufsz, format, arg);
} // vsnprintf_s

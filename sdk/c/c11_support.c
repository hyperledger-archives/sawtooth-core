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

#include <errno.h>
#include "c11_support.h"

#ifndef __STDC_LIB_EXT1__
int strncpy_s(char *dest, size_t sizeInBytes, const char *src, size_t count)
{
    if (count == 0 && dest == NULL && sizeInBytes == 0) {
        return 0;
    }

    if (dest == NULL || sizeInBytes <= 0) {
        return EINVAL;
    }

    if (count == 0) {
        *dest = 0;
        return 0;
    }

    if (src == NULL) {
        *dest = 0;
        return EINVAL;
    }

    char *p = dest;
    size_t availableSize = sizeInBytes;

    if (count == ((size_t) - 1)) {
        while ((*p++ = *src++) != 0 && --availableSize > 0);
    } else {
        while ((*p++ = *src++) != 0 && --availableSize > 0 && --count > 0);
        if (count == 0) {
            p = NULL;
        }
    }

    if (availableSize == 0)
    {
        if (count == ((size_t) - 1))
        {
            dest[sizeInBytes - 1] = 0;
            return STRUNCATE;
        }
        *dest = 0;
        return ERANGE;
    }
    return 0;
}

#endif // #ifdef __STDC_LIB_EXT1__

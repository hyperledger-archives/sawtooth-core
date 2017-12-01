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

#include <stdlib.h>
#include <stdarg.h>

// g++ 5.4 provides support already for the following
//
// snprintf
//
// g++ 5.4 does not provide support for the following optional C11 functions:
//
// memset_s
// strncpy_s
// vsnprintf_s

// If the compiler has been built with optional extensions, then we can have
// some of the missing functions made available by defining the appropriate
// preprocessor define before including string.h
#ifdef __STDC_LIB_EXT1__
    #define __STDC_WANT_LIB_EXT1__ 1
#else
    int memset_s(void *dest, size_t max, int c, size_t count);
    int memcpy_s(void *dest, size_t sizeInBytes, const void *src, size_t count);
    int strncpy_s(char *dest, size_t sizeInBytes, const char *src, size_t count);
    int strnlen_s(const char *str, size_t sizeInBytes);
#endif // #ifdef __STDC_LIB_EXT1__

#include <string.h>

#ifndef STRUNCATE
#define STRUNCATE 80
#endif

// It turns out that Microsoft has two versions of this function...one that has
// the same signature as the C11 standard and one of their own
int vsnprintf_s(
    char *buffer,
    size_t bufsz,
    const char* format,
    va_list arg);
int vsnprintf_s(
    char* buffer,
    size_t bufsz,
    size_t count,
    const char* format,
    va_list arg);

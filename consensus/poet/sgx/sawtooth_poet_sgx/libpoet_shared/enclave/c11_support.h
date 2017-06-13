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

// The SGX SDK has support for:
//
// memset_s
// snprintf
//
// The SGX SDK does not have support for:
//
// strncpy_s
// vsnprintf_s

#include <string.h>
#include <stdio.h>

#define strncpy_s(dest, size, src, count) strncpy(dest, src, count)
#define vsnprintf_s(str, size, format, args) vsnprintf(str, size, format, args)

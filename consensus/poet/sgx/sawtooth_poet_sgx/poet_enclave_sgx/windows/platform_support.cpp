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

#include <Windows.h>
#include "platform_support.h"

// Windows-specific ways to do platform-independent things

double CurrentTime()
{
    SYSTEMTIME st_epoc;
    FILETIME ft_epoc;
    ULARGE_INTEGER epoc;
    SYSTEMTIME st_now;
    FILETIME ft_now;
    ULARGE_INTEGER now;
    ULARGE_INTEGER now_since_epoc;
    long now_seconds;

    st_epoc.wYear = 1970;
    st_epoc.wMonth = 1;
    st_epoc.wDay = 1;
    st_epoc.wDayOfWeek = 4;
    st_epoc.wHour = 0;
    st_epoc.wMinute = 0;
    st_epoc.wSecond = 0;
    st_epoc.wMilliseconds = 0;

    SystemTimeToFileTime(&st_epoc, &ft_epoc);
    epoc.LowPart = ft_epoc.dwLowDateTime;
    epoc.HighPart = ft_epoc.dwHighDateTime;

    GetSystemTime(&st_now);
    SystemTimeToFileTime(&st_now, &ft_now);
    now.LowPart = ft_now.dwLowDateTime;
    now.HighPart = ft_now.dwHighDateTime;

    now_since_epoc.QuadPart = now.QuadPart - epoc.QuadPart;

    now_seconds = (long) (now_since_epoc.QuadPart / 10000000L);
    return now_seconds + st_now.wMilliseconds / 1000.0;
}  // CurrentTime

# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------
import time


def secs_to_date(secs, time_zone):
    seconds = float(secs)
    if time_zone:
        seconds -= int(time_zone) * 60
    sample_time = time.gmtime(seconds)
    # Remove any leading 0 on the month
    date_str = time.strftime("%m/%d/%Y", sample_time)
    if date_str[0] == '0':
        date_str = date_str[1:]
    return date_str


def secs_to_day(secs, time_zone):
    seconds = float(secs)
    if time_zone:
        seconds -= int(time_zone) * 60
    sample_time = time.gmtime(seconds)
    # Remove any leading 0 on the month
    date_str = time.strftime("%b %d, %Y - %A", sample_time)
    if date_str[0] == '0':
        date_str = date_str[1:]
    return date_str


def secs_to_time(secs, time_zone):
    seconds = float(secs)
    if time_zone:
        seconds -= int(time_zone) * 60
    sample_time = time.gmtime(seconds)
    # Remove any leading 0 on the hour
    time_str = time.strftime("%I:%M:%S %p", sample_time)
    if time_str[0] == '0':
        time_str = time_str[1:]
    return time_str


def secs_to_datetime(secs, time_zone):
    return secs_to_time(secs, time_zone) + " " + secs_to_date(secs, time_zone)

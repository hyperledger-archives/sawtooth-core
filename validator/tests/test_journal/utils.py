# Copyright 2016 Intel Corporation
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


class TimeOut:
    def __init__(self, wait):
        self.wait_time = wait
        self.expire_time = time.time() + wait

    def is_timed_out(self):
        return time.time() > self.expire_time

    def __call__(self, *args, **kwargs):
        return time.time() > self.expire_time


def wait_until(lbd, time_out=None):
    end_time = None
    if time_out is not None:
        end_time = time.time() + time_out

    while (end_time is None
           or time.time() < end_time) and \
            not lbd():
        time.sleep(0.1)

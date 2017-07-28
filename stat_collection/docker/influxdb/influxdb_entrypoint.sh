#!/usr/bin/env sh
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

if [ ! -f "/var/lib/influxdb/.init" ]; then  
  exec influxd $@ &

  until wget -q "http://localhost:8086/ping" 2> /dev/null; do
    sleep 1
  done

  curl -i -XPOST "http://localhost:8086/query" --data-urlencode "q=CREATE DATABASE metrics"

  touch "/var/lib/influxdb/.init"

  kill -s TERM %1
fi

exec influxd $@

# Copyright 2018 Cargill Incorporated
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

FROM ubuntu:xenial

RUN echo "deb http://repo.sawtooth.me/ubuntu/ci xenial universe" >> /etc/apt/sources.list \
 && (apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 8AA7AF1F1091A5FD \
 || apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 8AA7AF1F1091A5FD) \
 && apt-get update \
 && apt-get install -y -q --allow-downgrades \
    git \
    python3

RUN apt-get install -y -q --allow-downgrades \
    python3-grpcio \
    python3-grpcio-tools \
    python3-protobuf

RUN apt-get install -y -q --allow-downgrades \
    python3-colorlog \
    python3-requests \
    python3-toml \
    python3-yaml \
    python3-secp256k1

RUN apt-get install -y -q \
    python3-cov-core \
    python3-nose2 \
    python3-pip

RUN pip3 install \
    coverage --upgrade

ENV PATH=$PATH:/project/sawtooth-core/bin

WORKDIR /project/sawtooth-core

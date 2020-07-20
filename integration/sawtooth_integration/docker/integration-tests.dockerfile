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

FROM ubuntu:bionic

RUN apt-get update \
 && apt-get install gnupg -y

RUN echo "deb [arch=amd64] http://repo.sawtooth.me/ubuntu/nightly bionic universe" >> /etc/apt/sources.list \
 && (apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 44FC67F19B2466EA \
 || apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 44FC67F19B2466EA) \
 && apt-get update

RUN apt-get install -y -q \
    apt-transport-https \
    curl \
    python3-aiohttp \
    python3-cachetools \
    python3-cbor \
    python3-colorlog \
    python3-cov-core \
    python3-cryptography-vectors \
    python3-cryptography \
    python3-dev \
    python3-lmdb \
    python3-nose2 \
    python3-pip \
    python3-protobuf \
    python3-pyformance \
    python3-netifaces \
    python3-requests \
    python3-sawtooth-intkey \
    python3-sawtooth-xo \
    python3-secp256k1 \
    python3-toml \
    python3-yaml \
    python3-zmq \
    software-properties-common

RUN pip3 install \
    coverage --upgrade

RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - \
 && add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) \
         stable"

RUN apt-get update && apt-get install -y -q \
    docker-ce

ENV PATH=$PATH:/project/sawtooth-core/bin

WORKDIR /project/sawtooth-core

# Copyright 2018 Bitwise IO, Inc.
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

# docker build -f families/block_info/Dockerfile -t sawtooth-block-info-tp-local .

FROM ubuntu:bionic

RUN apt-get update \
 && apt-get install -y \
 curl \
 gcc \
 libssl-dev \
 libzmq3-dev \
 pkg-config \
 unzip

# For Building Protobufs
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y \
 && curl -OLsS https://github.com/google/protobuf/releases/download/v3.5.1/protoc-3.5.1-linux-x86_64.zip \
 && unzip protoc-3.5.1-linux-x86_64.zip -d protoc3 \
 && rm protoc-3.5.1-linux-x86_64.zip

ENV PATH=$PATH:/project/sawtooth-core/bin:/protoc3/bin:/root/.cargo/bin \
    CARGO_INCREMENTAL=0

WORKDIR /project/sawtooth-core/

CMD cd families/block_info/sawtooth_block_info \
 && echo "\033[0;32m--- Building block-info ---\n\033[0m" \
 && rm -rf ./bin/ \
 && mkdir -p ./bin/ \
 && cargo build --release \
 && cp ./target/release/block-info-tp ./bin/block-info-tp

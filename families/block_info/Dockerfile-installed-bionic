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

# docker build -f families/block_info/Dockerfile-installed-bionic -t sawtooth-block-info-tp .

# -------------=== block-info rust build ===-------------
FROM ubuntu:bionic as block-info-rust-builder

ENV VERSION=AUTO_STRICT

RUN apt-get update \
 && apt-get install -y \
 curl \
 gcc \
 libssl-dev \
 libzmq3-dev \
 python3 \
 git \
 pkg-config \
 unzip

# For Building Protobufs
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y \
 && curl -OLsS https://github.com/google/protobuf/releases/download/v3.5.1/protoc-3.5.1-linux-x86_64.zip \
 && unzip protoc-3.5.1-linux-x86_64.zip -d protoc3 \
 && rm protoc-3.5.1-linux-x86_64.zip

ENV PATH=$PATH:/protoc3/bin
RUN /root/.cargo/bin/cargo install cargo-deb

COPY . /project/sawtooth-core

WORKDIR /project/sawtooth-core/families/block_info/sawtooth_block_info

RUN export VERSION=$(../../../bin/get_version) \
 && sed -i -e s/version.*$/version\ =\ \"${VERSION}\"/ Cargo.toml \
 && /root/.cargo/bin/cargo deb --deb-version $VERSION

# -------------=== block-info rust docker build ===-------------
FROM ubuntu:bionic

COPY --from=block-info-rust-builder /project/sawtooth-core/families/block_info/sawtooth_block_info/target/debian/sawtooth-block-info-tp_*.deb /tmp

RUN apt-get update \
&& apt-get install -y \
  libssl-dev \
  libzmq3-dev \
  systemd \
 && dpkg -i /tmp/sawtooth-block-info-*.deb || true \
 && apt-get -f -y install

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

# docker build -f validator/Dockerfile -t sawtooth-validator-local .

# -------------===  build ===-------------

FROM ubuntu:xenial

RUN echo "deb http://repo.sawtooth.me/ubuntu/ci xenial universe" >> /etc/apt/sources.list \
 && (apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 8AA7AF1F1091A5FD \
 || apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 8AA7AF1F1091A5FD) \
 && apt-get update

RUN apt-get install -y -q --allow-downgrades \
    git \
    python3 \
    python3-stdeb

RUN apt-get install -y -q --allow-downgrades \
    python3-grpcio \
    python3-grpcio-tools \
    python3-protobuf

RUN apt-get install -y -q --allow-downgrades \
    libssl-dev \
    openssl \
    pkg-config \
    python3-cbor \
    python3-colorlog \
    python3-cryptography>=1.7.1 \
    python3-dev \
    python3-lmdb \
    python3-netifaces=0.10.4-0.1build2 \
    python3-pyformance \
    python3-secp256k1 \
    python3-toml \
    python3-yaml \
    python3-zmq \
    unzip

RUN curl -OLsS https://github.com/google/protobuf/releases/download/v3.5.1/protoc-3.5.1-linux-x86_64.zip \
 && unzip protoc-3.5.1-linux-x86_64.zip -d protoc3 \
 && rm protoc-3.5.1-linux-x86_64.zip

RUN curl https://sh.rustup.rs -sSf > /usr/bin/rustup-init \
 && chmod +x /usr/bin/rustup-init \
 && rustup-init -y

ENV PATH=$PATH:/project/sawtooth-core/bin:/protoc3/bin:/project/sawtooth-core/bin:/root/.cargo/bin \
    CARGO_INCREMENTAL=0

RUN ln -s /usr/bin/python3 /usr/bin/python

RUN mkdir -p /etc/sawtooth/keys
RUN mkdir -p /var/lib/sawtooth
RUN mkdir -p /var/log/sawtooth

ENV PATH=$PATH:/project/sawtooth-core/bin

WORKDIR /project/sawtooth-core

CMD echo "\033[0;32m--- Building validator ---\n\033[0m" \
 && ./bin/protogen \
 && cd validator \
 && if [ -d "debian" ]; then rm -rf debian; fi \
 && python3 setup.py clean --all \
 && python3 setup.py --command-packages=stdeb.command debianize \
 && if [ -d "packaging/ubuntu" ]; then cp -R packaging/ubuntu/* debian/; fi \
 && if [ -d "bin" ]; then rm -rf bin; fi \
 && mkdir bin \
 && if [ -d "lib" ]; then rm -rf lib; fi \
 && mkdir lib \
 && cargo build --release \
 && cp ./target/release/sawtooth-validator bin/sawtooth-validator \
 && cp ./target/release/libsawtooth_validator.so lib/libsawtooth_validator.so

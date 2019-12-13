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

# docker build -f cli/Dockerfile-installed-bionic -t sawtooth-cli-builder .

# -------------=== cli build ===-------------
FROM ubuntu:bionic as cli-builder

RUN apt-get update \
 && apt-get install gnupg -y

ENV VERSION=AUTO_STRICT

RUN echo "deb http://repo.sawtooth.me/ubuntu/nightly bionic universe" >> /etc/apt/sources.list \
 && (apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 44FC67F19B2466EA \
 || apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 44FC67F19B2466EA) \
 && apt-get update \
 && apt-get install -y -q \
    git \
    python3 \
    python3-protobuf \
    python3-stdeb \
    python3-toml \
    python3-grpcio-tools \
    python3-grpcio \
    python3-sawtooth-sdk

COPY . /project

RUN /project/bin/protogen \
 && cd /project/cli \
 && if [ -d "debian" ]; then rm -rf debian; fi \
 && python3 setup.py clean --all \
 && python3 setup.py --command-packages=stdeb.command debianize \
 && if [ -d "packaging/ubuntu" ]; then cp -R packaging/ubuntu/* debian/; fi \
 && dpkg-buildpackage -b -rfakeroot -us -uc


# -------------=== cli docker build ===-------------
FROM ubuntu:bionic

RUN apt-get update \
 && apt-get install gnupg -y

COPY --from=cli-builder /project/python3-sawtooth-cli*.deb /tmp

RUN echo "deb http://repo.sawtooth.me/ubuntu/ci bionic universe" >> /etc/apt/sources.list \
 && (apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 8AA7AF1F1091A5FD \
 || apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 8AA7AF1F1091A5FD) \
 && apt-get update \
 && dpkg -i /tmp/python3-sawtooth*.deb || true \
 && apt-get -f -y install \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

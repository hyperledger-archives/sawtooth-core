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

# docker build -f integration/Dockerfile-installed-bionic -t sawtooth-integration .

# -------------=== sawtooth integration build ===-------------

FROM ubuntu:bionic as sawtooth-integration-builder

RUN apt-get update \
 && apt-get install gnupg -y

ENV VERSION=AUTO_STRICT

RUN echo "deb http://repo.sawtooth.me/ubuntu/ci bionic universe" >> /etc/apt/sources.list \
 && (apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 8AA7AF1F1091A5FD \
 || apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 8AA7AF1F1091A5FD) \
 && apt-get update \
 && apt-get install -y -q \
    git \
    python3 \
    python3-stdeb

COPY . /project

RUN cd /project/integration/ \
 && if [ -d "debian" ]; then rm -rf debian; fi \
 && python3 setup.py clean --all \
 && python3 setup.py --command-packages=stdeb.command debianize \
 && if [ -d "packaging/ubuntu" ]; then cp -R packaging/ubuntu/* debian/; fi \
 && DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -b -rfakeroot -us -uc

 # -------------=== sawtooth-integration docker build ===-------------
FROM ubuntu:bionic

RUN apt-get update \
 && apt-get install gnupg -y

COPY --from=sawtooth-integration-builder /project/python3-sawtooth-integration*.deb /tmp

RUN echo "deb http://repo.sawtooth.me/ubuntu/ci bionic universe" >> /etc/apt/sources.list \
 && (apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 8AA7AF1F1091A5FD \
 || apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 8AA7AF1F1091A5FD) \
 && apt-get update \
 && dpkg -i /tmp/python3-sawtooth-*.deb || true \
 && apt-get -f -y install

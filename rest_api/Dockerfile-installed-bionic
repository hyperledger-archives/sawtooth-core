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

# docker build -f rest_api/Dockerfile-installed-bionic -t sawtooth-rest-api .

# -------------=== rest api build ===-------------

FROM ubuntu:bionic as rest-api-builder

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
    python3-aiodns \
    python3-aiohttp \
    python3-cchardet\
    python3-grpcio-tools \
    python3-grpcio \
    python3-protobuf \
    python3-pyformance \
    python3-sawtooth-sdk \
    python3-stdeb

COPY . /project

RUN /project/bin/protogen \
 && cd /project/rest_api/ \
 && if [ -d "debian" ]; then rm -rf debian; fi \
 && python3 setup.py clean --all \
 && python3 setup.py --command-packages=stdeb.command debianize \
 && if [ -d "packaging/ubuntu" ]; then cp -R packaging/ubuntu/* debian/; fi \
 && dpkg-buildpackage -b -rfakeroot -us -uc

 # -------------=== rest api docker build ===-------------
FROM ubuntu:bionic

RUN apt-get update \
 && apt-get install -y \
 gnupg \
 systemd

COPY --from=rest-api-builder /project/python3-sawtooth-rest-api*.deb /tmp

RUN echo "deb http://repo.sawtooth.me/ubuntu/nightly bionic universe" >> /etc/apt/sources.list \
 && (apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 44FC67F19B2466EA \
 || apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 44FC67F19B2466EA) \
 && apt-get update \
 && dpkg -i /tmp/python3-sawtooth-*.deb || true \
 && apt-get -f -y install \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

EXPOSE 4004/tcp
EXPOSE 8008

CMD ["sawtooth-rest-api"]

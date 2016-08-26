#!/bin/bash -x

set -e

if [ ! -f /etc/debian_version ]; then
    echo "Skipping $0"
    exit 0
fi

apt-get update -y

VER=$(lsb_release -sr)
 
if [ "$VER" = "16.04" ] ; then
    apt-get install -y -q \
        python-cryptography \
        python-service-identity \
        python-openssl \
        python-twisted-core
else
    apt-get install -y -q \
        python-enum34
fi 

apt-get install -y -q \
    python-twisted \
    python-twisted-web \
    python-dev \
    python-setuptools \
    python-pip \
    python-yaml \
    python-numpy \
    g++ \
    swig3.0 \
    libjson0 \
    libjson0-dev \
    libcrypto++-dev \
    git

if [ ! -f /usr/bin/swig ]; then
    ln -s /usr/bin/swig3.0 /usr/bin/swig
fi

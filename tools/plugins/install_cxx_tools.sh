#!/bin/bash -x

. /vagrant/conf.sh

set -e

if [ ! -f /etc/debian_version ]; then
    echo "Skipping $0"
    exit 0
fi

apt -y install cmake g++ libzmqpp-dev libcrypto++-dev liblog4cxx-dev
pip3 install cpplint

#protobuf deps
apt -y install autoconf automake libtool curl make unzip

cd /tmp
PROTOBUF3_CPP="protobuf-cpp-3.2.0.zip"
rm -rf protobuf
mkdir protobuf
cd protobuf
wget https://github.com/google/protobuf/releases/download/v3.2.0/${PROTOBUF3_CPP}
unzip ${PROTOBUF3_CPP}
cd protobuf-3.2.0
./configure
make

make check
make install
ldconfig # refresh shared library cache.



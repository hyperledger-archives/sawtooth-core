#!/bin/bash -x

. /vagrant/conf.sh

set -e

if [ ! -f /etc/debian_version ]; then
    echo "Skipping $0"
    exit 0
fi

apt-get -y install cmake g++ libzmqpp-dev libcrypto++-dev liblog4cxx-dev protobuf
pip3 install cpplint


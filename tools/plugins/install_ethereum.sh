#!/bin/bash -x

set -e

if [ -f /etc/debian_version ]; then
    apt-get install software-properties-common
    add-apt-repository -y ppa:ethereum/ethereum
    add-apt-repository -y ppa:ethereum/ethereum-dev
    apt-get update
    apt-get install -y ethereum
else
    echo "Skipping Ethereum installation on this platform."
fi


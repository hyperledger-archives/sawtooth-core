#!/bin/bash -x

set -e

if [ ! -e /usr/bin/zypper ]; then
    echo "Skipping $0"
    exit 0
fi

zypper install -y \
    python-setuptools \
    git \
    tar \
    vim


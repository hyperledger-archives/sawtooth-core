#!/bin/bash

set -e

apt-get install -y \
    cython

apt-get remove -y \
    python-enum34

pip install \
    enum34 \
    grpcio-tools

#!/bin/bash

set -e

apt-get install -y \
    cython

pip install \
    enum34 \
    grpcio-tools

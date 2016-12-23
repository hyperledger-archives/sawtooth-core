#!/usr/bin/env bash

set -e

apt-get update && apt-get install -y \
    python3-zmq \
    libzmq-dev

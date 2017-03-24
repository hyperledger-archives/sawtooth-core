#!/bin/bash -x

set -e

if [ -f /etc/debian_version ]; then
    echo "deb http://repo.sawtooth.me/ xenial universe" >> /etc/apt/sources.list
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 6B58B1AC10FB5F63
    apt-get update -y
elif [ -f /etc/redhat-release ]; then
    yum upgrade -y
else
    echo "Skipping $0"
    exit 0
fi

#!/bin/bash -x

set -e

if [ -f /etc/debian_version ]; then
    echo "deb http://repo.sawtooth.me/ubuntu/nightly xenial universe" >> /etc/apt/sources.list
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 44FC67F19B2466EA
    apt-get update -y
elif [ -f /etc/redhat-release ]; then
    yum upgrade -y
else
    echo "Skipping $0"
    exit 0
fi

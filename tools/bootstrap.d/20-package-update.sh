#!/bin/bash -x

set -e

if [ -f /etc/debian_version ]; then
    apt-get update -y
elif [ -f /etc/redhat-release ]; then
    yum upgrade -y
else
    echo "Skipping $0"
    exit 0
fi

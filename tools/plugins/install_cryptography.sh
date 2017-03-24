#!/bin/bash

set -e

# Make sure that the cryptography package dependencies are installed
apt-get install build-essential libssl-dev libffi-dev python3-dev

apt-get install -y -q \
   python3-cryptography=1.7.2-1

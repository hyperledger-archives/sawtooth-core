#!/bin/bash

set -e

# Make sure that the cryptography package dependencies are installed
apt-get install build-essential libssl-dev libffi-dev python3-dev

pip3 install \
   cryptography 

#!/bin/bash

set -e

apt-get install -y -q --allow-downgrades \
    python3-aiohttp=1.3.5-1 \
    python3-chardet=2.3.0-1

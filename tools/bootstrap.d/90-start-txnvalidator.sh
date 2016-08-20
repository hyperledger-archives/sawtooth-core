#!/bin/bash

[[ -e /project ]] || exit 1

. /vagrant/conf.sh

if [[ "$START_TXNVALIDATOR" != "yes" ]]; then
    echo "Skipping: $0"
    exit 0
fi

set -e

if [ -f /etc/init/sawtooth-validator.conf ]; then
    start sawtooth-validator
fi

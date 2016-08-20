#!/bin/bash -x

set -e

if [ ! -f /etc/debian_version ]; then
    echo "Skipping $0"
    exit 0
fi

cd /vagrant

source /etc/lsb-release
echo "deb http://download.rethinkdb.com/apt $DISTRIB_CODENAME main" \
    | tee /etc/apt/sources.list.d/rethinkdb.list

wget -qO- https://download.rethinkdb.com/apt/pubkey.gpg | apt-key add -
apt-get update
apt-get install -y rethinkdb

mkdir -p /opt/rethinkdb/data

cp guest-files/rethinkdb.instance1.conf \
    /etc/rethinkdb/instances.d/instance1.conf

/etc/init.d/rethinkdb restart

# Required for ledger_sync
pip install rethinkdb \
            cachetools

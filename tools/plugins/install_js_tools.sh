#!/bin/bash -x

. /vagrant/conf.sh

set -e

if [ ! -f /etc/debian_version ]; then
    echo "Skipping $0"
    exit 0
fi

cd /vagrant

# Run setup-node.sh
if [ ! -e cache/setup-node.sh ]; then
    curl -s -S -o cache/setup-node.sh https://deb.nodesource.com/setup_6.x
    chmod 755 cache/setup-node.sh
fi
./cache/setup-node.sh

# Run setup-node.sh
apt-get install -y -q \
    nodejs

sudo -i -u $VAGRANT_USER npm set progress=false

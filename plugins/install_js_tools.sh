#!/bin/bash -x

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

# Install lein
if [ ! -e cache/lein ]; then
    curl -s -S -o cache/lein \
       https://raw.githubusercontent.com/technomancy/leiningen/stable/bin/lein
    chmod +x cache/lein
fi
mv cache/lein /usr/local/bin/lein

# Run setup-node.sh
apt-get install -y -q \
    rlwrap \
    phantomjs \
    nodejs \
    ruby2.0 \
    openjdk-7-jdk

gem2.0 install sass

sudo -i -u vagrant npm set progress=false

npm install -g forever


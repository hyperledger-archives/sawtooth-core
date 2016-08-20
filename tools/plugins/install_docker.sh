#!/bin/bash -x

set -e

if [ ! -f /etc/debian_version ]; then
    echo "Skipping $0"
    exit 0
fi

apt-get install -y apt-transport-https ca-certificates
VER=$(lsb_release -sr)

apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 58118E89F3A912897C070ADBF76221572C52609D

if [ "$VER" = "16.04" ] ; then
echo "deb https://apt.dockerproject.org/repo ubuntu-xenial main" > /etc/apt/sources.list.d/docker.list
echo "deb https://apt.dockerproject.org/repo ubuntu-xenial main" > /etc/apt/sources.list.d/docker.list
else
echo "deb https://apt.dockerproject.org/repo ubuntu-trusty main" > /etc/apt/sources.list.d/docker.list
fi
apt-get update
apt-get install -y --show-progress linux-image-extra-$(uname -r) apparmor docker-engine

 usermod -aG docker vagrant

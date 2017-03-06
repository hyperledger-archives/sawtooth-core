#!/bin/bash -x

. /vagrant/conf.sh

set -e

mkdir -p /home/$VAGRANT_USER/sawtooth
mkdir -p /home/$VAGRANT_USER/sawtooth/logs
mkdir -p /home/$VAGRANT_USER/sawtooth/data
mkdir -p /home/$VAGRANT_USER/sawtooth/keys
chown -R $VAGRANT_USER:$VAGRANT_USER /home/$VAGRANT_USER/sawtooth

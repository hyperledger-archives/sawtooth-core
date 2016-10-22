#!/bin/bash -x

. /vagrant/conf.sh

set -e

mkdir /home/$VAGRANT_USER/sawtooth
mkdir /home/$VAGRANT_USER/sawtooth/logs
mkdir /home/$VAGRANT_USER/sawtooth/data
mkdir /home/$VAGRANT_USER/sawtooth/keys
chown -R $VAGRANT_USER:$VAGRANT_USER /home/$VAGRANT_USER/sawtooth

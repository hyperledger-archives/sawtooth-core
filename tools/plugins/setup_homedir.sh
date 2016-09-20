#!/bin/bash -x

set -e

mkdir /home/vagrant/sawtooth
mkdir /home/vagrant/sawtooth/logs
mkdir /home/vagrant/sawtooth/data
mkdir /home/vagrant/sawtooth/keys
chown -R vagrant:vagrant /home/vagrant/sawtooth

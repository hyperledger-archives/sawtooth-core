#!/bin/bash
rm -rf /home/vagrant/sawtooth
mkdir /home/vagrant/sawtooth
mkdir /home/vagrant/sawtooth/keys
mkdir /home/vagrant/sawtooth/data
mkdir /home/vagrant/sawtooth/logs
/project/sawtooth-core/bin/sawtooth keygen xo000 --key-dir /home/vagrant/sawtooth/keys
/project/sawtooth-core/bin/sawtooth admin poet0-genesis --keyfile /home/vagrant/sawtooth/keys/xo000.wif -F sawtooth_xo --node xo000

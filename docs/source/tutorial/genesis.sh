#!/bin/bash
rm -rf /home/vagrant/sawtooth
mkdir /home/vagrant/sawtooth
mkdir /home/vagrant/sawtooth/keys
mkdir /home/vagrant/sawtooth/data
mkdir /home/vagrant/sawtooth/logs
./bin/sawtooth keygen base000 --key-dir /home/vagrant/sawtooth/keys
./bin/sawtooth admin poet0-genesis --keyfile /home/vagrant/sawtooth/keys/base000.wif -F mktplace.transactions.market_place -F ledger.transaction.integer_key
echo {\"InitialConnectivity\": 0} > /home/vagrant/sawtooth/v0.json

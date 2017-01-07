#!/bin/bash
rm -rf /home/ubuntu/sawtooth
mkdir /home/ubuntu/sawtooth
mkdir /home/ubuntu/sawtooth/keys
mkdir /home/ubuntu/sawtooth/data
mkdir /home/ubuntu/sawtooth/logs
/project/sawtooth-core/bin/sawtooth keygen xo000 --key-dir /home/ubuntu/sawtooth/keys
/project/sawtooth-core/bin/sawtooth admin poet0-genesis --keyfile /home/ubuntu/sawtooth/keys/xo000.wif -F sawtooth_xo --node xo000

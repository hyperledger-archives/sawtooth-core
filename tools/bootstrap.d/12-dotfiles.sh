#!/bin/bash -x

grep -q "source /vagrant/guest-files/bashrc" /home/vagrant/.bashrc
if [ $? = 1 ]; then
    echo "source /vagrant/guest-files/bashrc" >> /home/vagrant/.bashrc
fi

mkdir -p /home/vagrant/.ssh
mkdir -p /root/.ssh

if [ -e /vagrant/ssh/id_rsa ]; then
    cp /vagrant/ssh/id_rsa /home/vagrant/.ssh/
    cp /vagrant/ssh/id_rsa /home/vagrant/.ssh/
    chmod 400 /home/vagrant/.ssh/id_rsa
fi

if [ -e /vagrant/ssh/known_hosts ]; then
    cp /vagrant/ssh/known_hosts /home/vagrant/.ssh/
    cp /vagrant/ssh/known_hosts /home/vagrant/.ssh/
    chmod 644 /home/vagrant/.ssh/known_hosts
fi


#!/bin/bash -x

. /vagrant/conf.sh

homedir="/home/$VAGRANT_USER"

grep -q "source /vagrant/guest-files/bashrc" $homedir/.bashrc
if [ $? = 1 ]; then
    echo "source /vagrant/guest-files/bashrc" >> $homedir/.bashrc
fi

mkdir -p $homedir/.ssh
mkdir -p /root/.ssh

if [ -e /vagrant/ssh/id_rsa ]; then
    cp /vagrant/ssh/id_rsa $homedir/.ssh/
    cp /vagrant/ssh/id_rsa $homedir/.ssh/
    chmod 400 $homedir/.ssh/id_rsa
fi

if [ -e /vagrant/ssh/known_hosts ]; then
    cp /vagrant/ssh/known_hosts $homedir/.ssh/
    cp /vagrant/ssh/known_hosts $homedir/.ssh/
    chmod 644 $homedir/.ssh/known_hosts
fi


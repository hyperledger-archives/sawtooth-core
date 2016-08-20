#!/bin/bash -x

. /vagrant/conf.sh

if [[ "$SETUP_SAWTOOTH_ENVIRONMENT" == "yes" ]]; then
    cp /vagrant/guest-files/local-env.sh /etc/profile.d/
fi


if [[ "$SETUP_SAWTOOTH_PATH" == "yes" ]]; then
    cp -f /vagrant/guest-files/local-path.sh /etc/profile.d/
fi





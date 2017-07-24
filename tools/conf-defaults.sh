#!/usr/bin/env bash

[[ -z "$SETUP_SAWTOOTH_ENVIRONMENT" ]] && export SETUP_SAWTOOTH_ENVIRONMENT=yes
[[ -z "$SETUP_SAWTOOTH_PATH" ]] && export SETUP_SAWTOOTH_PATH=no
[[ -z "$PLUGINS" ]] && export PLUGINS="setup_homedir install_go_tools install_sphinx install_grpc install_bitcoin install_aiohttp install_js_tools install_docker install_secp256k1 install_cryptography install_cxx_tools install_psycopg2"

function get_vagrant_user() {
    for user in vagrant ubuntu
    do
        if id $user > /dev/null 2>&1; then
            echo $user
            return
        fi
    done
}

if [[ -e /vagrant ]] && [[ -z "$VAGRANT_USER" ]]; then
    export VAGRANT_USER=$(get_vagrant_user)
    if [ -z "$VAGRANT_USER" ]; then
        echo "Could not determine vagrant user." 1>&2
        exit 1
    fi
fi

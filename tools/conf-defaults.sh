#!/usr/bin/env bash

[[ -z "$SETUP_SAWTOOTH_ENVIRONMENT" ]] && export SETUP_SAWTOOTH_ENVIRONMENT=yes
[[ -z "$SETUP_SAWTOOTH_PATH" ]] && export SETUP_SAWTOOTH_PATH=no
[[ -z "$PLUGINS" ]] && export PLUGINS="setup_homedir build_ubuntu_deps install_ubuntu_deps install_sphinx install_lmdb"

function get_vagrant_user() {
    for user in vagrant ubuntu
    do
        if id $user > /dev/null 2>&1; then
            echo $user
	    return
        fi
    done
}

if [[ -z "$VAGRANT_USER" ]]; then
    export VAGRANT_USER=$(get_vagrant_user)
    if [ -z "$VAGRANT_USER" ]; then
        echo "Could not determine vagrant user." 1>&2
        exit 1
    fi
fi

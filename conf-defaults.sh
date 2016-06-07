#!/usr/bin/env bash

[[ -z "$INSTALL_TYPE" ]] && export INSTALL_TYPE=none
[[ -z "$START_TXNVALIDATOR" ]] && export START_TXNVALIDATOR=no
[[ -z "$SETUP_SAWTOOTH_ENVIRONMENT" ]] && export SETUP_SAWTOOTH_ENVIRONMENT=yes
[[ -z "$SETUP_SAWTOOTH_PATH" ]] && export SETUP_SAWTOOTH_PATH=no
[[ -z "$PLUGINS" ]] && export PLUGINS="build_ubuntu_deps install_ubuntu_deps install_sphinx install_beautifulsoup4"


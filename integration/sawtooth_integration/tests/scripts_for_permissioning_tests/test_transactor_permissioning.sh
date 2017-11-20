#!/usr/bin/env bash

# This file is used in test_transactor_permissioning.yaml and is run
# before the validator starts up.

sawtooth keygen alice
sawtooth keygen bob
sawtooth keygen chuck
sawtooth keygen carol
sawtooth keygen dave
sawtooth keygen mallory
sawtooth keygen walter
mkdir /etc/sawtooth/policy
cat > /etc/sawtooth/policy/allow_dave_walter_deny_chuck_mallory << EOM
DENY_KEY $(cat /root/.sawtooth/keys/chuck.pub)
DENY_KEY $(cat /root/.sawtooth/keys/mallory.pub)
PERMIT_KEY $(cat /root/.sawtooth/keys/dave.pub)
PERMIT_KEY $(cat /root/.sawtooth/keys/walter.pub)
PERMIT_KEY $(cat /root/.sawtooth/keys/alice.pub)
PERMIT_KEY $(cat /root/.sawtooth/keys/bob.pub)
PERMIT_KEY $(cat /root/.sawtooth/keys/carol.pub)
EOM

cat > /etc/sawtooth/policy/deny_carol_from_xo << EOM
DENY_KEY $(cat /root/.sawtooth/keys/carol.pub)
PERMIT_KEY *
EOM

cat > /etc/sawtooth/policy/deny_dave_from_sending_batches << EOM
DENY_KEY $(cat /root/.sawtooth/keys/dave.pub)
PERMIT_KEY *
EOM

cat > /etc/sawtooth/validator.toml << EOM
[permissions]
transactor = "allow_dave_walter_deny_chuck_mallory"
"transactor.transaction_signer.xo" = "deny_carol_from_xo"
"transactor.batch_signer" = "deny_dave_from_sending_batches"
EOM

sawset proposal create -k /root/.sawtooth/keys/walter.priv sawtooth.identity.allowed_keys=$(cat /root/.sawtooth/keys/walter.pub) -o config.batch

Sawtooth Battleship
===================

Introduction
------------

Sawtooth is an implementation of the game Battleship for the Hyperledger Sawtooth platform. It
provides a transaction processor and CLI.


Example Usage
-------------

If you don't already have a copy of the Sawtooth platform running, you can start a copy by running
this command from the root `sawtooth-core` directory:

    docker-compose -f docker/compose/sawtooth-default.yaml up

To start the transaction processor, run this command from this directory (i.e.
`families/battleship`):

    cargo run --bin battleship-tp -- -vv -C http://localhost:8008/

You can then use the cli by running it like this:

    cargo run --bin battleship-cli -- COMMAND

Run `cargo run --bin battleship-cli -- --help` to see the available commands. You will need at least two keys
generated and placed in `~/.sawtooth/keys/` to play a game. To generate a sample game, you can run
the `play` example that will generate two random keys and use them to play a game:

    cargo run --example play

Documentation
-------------

For documentation, run

    cargo doc --no-deps

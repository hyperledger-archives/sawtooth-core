# Ledger Sync

This tool synchronizes the state of the ledger chain with the Bond UI's RethinkDB instance.

## Running the tool

The ledger sync tool, in it's current form runs well in the sawtooth-core vagrant
environment.  In your `bashrc-local` file, add the `ledger_sync` directory to your `PYTHONPATH`.

```
PYTHONPATH=$PYTHONPATH:/project/sawtooth-core/extensions/bond/ui/ledger_sync
export PYTHONPATH
```

It can be executed by running the following script:

```
> <ledger_sync_home>/scripts/syncledger
```
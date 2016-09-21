# Ledger Sync

This tool synchronizes the state of the ledger chain with Ledger Explorer's RethinkDB instance.

## Running the tool

The ledger sync tool, in it's current form runs well in the sawtooth-core vagrant
environment.  In your `bashrc-local` file, add the `ledger_sync` directory to your `PYTHONPATH`.

It can be executed via: 

```
> <ledger_sync_home>/scripts/syncledger
```

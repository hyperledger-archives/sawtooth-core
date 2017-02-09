# Sawtooth Bond API Server

The API server and static resource host.

# Development

How to setup and run the app in development.

## Prerequisites

* [Node JS 6 or above](https://nodejs.org/en/download/current/)
* [RethinkDB](https://www.rethinkdb.com/)
* [Python 2.7](https://www.python.org/downloads/release/python-2711/)
* [pip](https://pypi.python.org/pypi/pip)

## Environment Variables:

* PORT - the server port; defaults to 3000
* DB_HOST - the database host; defaults to `localhost`
* DB_PORT - the database port: defaults to 28015
* DB_NAME - the database name: defaults to `bond``
* LEDGER_URL - The base URI for the ledger service; defaults
    to `http://localhost:8800`
* NODE_ENV - Set this to `production`

## Setting Up Your Environment

To setup both the server and client, from the `/ui` directory, run

  ```
  > ./scripts/setup.sh
  ```

_Or_, to just setup the server, from the `/server` directory, run:

  1. Install server dependencies

    ```
    > ./scripts/bootstrap.sh
    ```

  2. Initialize the database

    ```
    > ./scripts/build.sh
    ```

    The database-related environment variables are used with this script, as
    well

  3. Install test dependencies

    ```
    > pip install cbor pybitcointools
    ```

## Running Locally

With a validator and `ledger_sync` running, start the server with

  ```
  > npm start
  ```

The site will be available at [localhost:3000](http://localhost:3000/").

All of the environment variables above are used with this script. Adjusting the
environment variables for production might look like this:

```
> cd <ui-dir>/server
> PORT=80 \
  DB_HOST=someserver.someplace \
  DB_PORT=29000 \
  DB_NAME=custom_bond_db \
  LEDGER_URL=http://someledgerserver.someplace:8800 \
  npm start
```

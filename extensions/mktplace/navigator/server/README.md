# Ledger Explorer API Server

The API server and static resource host.

# Environment Variables:

* PORT - the server port; defaults to 3000
* DB_HOST - the database host; defaults to `localhost`
* DB_PORT - the database port: defaults to 28015
* DB_NAME - the database name: defaults to `ledger`
* LEDGER_HOST - The host for the ledger service; defaults to `localhost`
* LEDGER_PORT - The port for the ledger service; defaults to 8800
* NODE_ENV - Set this to `production`

# Development
 
How to setup and run the app in development.
 
## Prerequisites
 
* [Node JS 6 or above](https://nodejs.org/en/download/current/)
* [Yarn](https://yarnpkg.com/)
* [RethinkDB](https://www.rethinkdb.com/)
* [Python 2.7](https://www.python.org/downloads/release/python-2711/)
* [pip](https://pypi.python.org/pypi/pip)

## Setting Up Your Environment

1. Install server dependencies

    ```
    > cd <ledger-explorer-root-dir>/server
    > npm install
    ```

2. Initialize the database

    ```
    > node scripts/bootstrap_db.js
    ```

    The database-related environment variables are used with this script, as
    well


## Running Locally

Simply start the server via

```
> cd <ledger-explorer-root-dir>/server
> npm start
```

The site will be available at [localhost:3000](http://localhost:3000/").

All of the environment variables above are used with this script.


# Production

Before running, you'll need to be sure that the dependencies are up to date
and the JS/CSS client code is built:

```
> cd <ledger-explorer-root-dir>/client
> ./scripts/build.sh
```

All the environment variables are used by `server.js`.  Adjusting the
environment variables for production might look like this:

```
> cd <ledger-explorer-root-dir>/server
> PORT=80 \
  DB_HOST=someserver.someplace \
  DB_PORT=29000 \
  DB_NAME=custom_explorer_db \
  LEDGER_URL=http://someledgerserver.someplace:8800 \
  node server.js
```

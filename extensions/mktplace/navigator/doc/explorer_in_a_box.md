# Explorer in a Box

Running a complete Marketplace Ledger Explorer package


## Prerequisites

Install the following tools:

* [Vagrant](https://www.vagrantup.com/)
* Depending on your OS, you may also need
[VirtualBox](https://www.virtualbox.org/wiki/Downloads)


## Usage

For an entirely out-of-the-box experience (Marketplace Ledger Explorer server,
a RethinkDB instance, an Intel wallet simulator, and a validator), you can
simply start the vagrant image by running:

```
> cd <sawtooth-ledger-explorer>/dev-tools
> vagrant up
```

This will take some time, as it installs all the necessary pieces to run all
of the components.  Once this has completed, you will find the web client
running at [localhost:3000](http://localhost:3000).


## Advanaced options

If you are using a separate validator instance, you may modify two settings
to both specify its location, and to disable starting up a validator in the VM.

First, create the file `guest-files/ledger-explorer-settings` with the
following variable:

```
LEDGER_URL=http://<validator_host>:<validator_port>
```

Second, create the file `conf-local.sh` with the following setting configured:

```
# ...

export START_TXNVALIDATOR=no

# ...
```


Likewise, if you are using your own instance of an Intel Wallet, you can
disable the simulator with the following setting in `conf-local.sh`:


```
# ...

export START_WALLET_SIMULATOR=no

# ...
```

Example of both the files above can be found in their respective locations.


### Proxy Settings

If you are behind a proxy, you'll need to install the
[vagrant-proxyconf](https://github.com/tmatilai/vagrant-proxyconf)
plugin before starting your vagrant image::

```
> vagrant plugin insall vagrant-proxyconf
```

If you also are using a caching server for maven artifacts, you can configure
by adding a `profiles.clj` file in the `guest-files` directory.

For example:

```
{:user
  {:mirrors {"central" {:name "your-central-mirror"
                        :url "https://your-mirror.your-domain.com/repo"}}}}
```


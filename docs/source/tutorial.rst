 
.. _tutorial:

********
Tutorial
********

Overview
========

This tutorial walks through the process of setting up a virtual development
environment for the Distributed Ledger using Vagrant and VirtualBox. At the
end, you will have a running validator network and be able to use client
commands to interact with it.

Commands in this tutorial can be run via Terminal.app on MacOS, Git Bash on
Windows, etc.

Prerequisites
=============

The following tools are required:

* `Vagrant <https://www.vagrantup.com/downloads.html>`_ (1.9.0 or later)
* `VirtualBox <https://www.virtualbox.org/wiki/Downloads>`_ (5.0.10 r104061
  or later)

On Windows, you will also need to install:

* `Git for Windows <http://git-scm.com/download/win>`_

Git for Windows will provide not only git to clone the repositories, but also
ssh which is required by Vagrant. During installation, accept all defaults.

Clone Repository
================

Open up a terminal and run the following:

.. code-block:: console

   % cd $HOME
   % mkdir project
   % cd project
   % git clone https://github.com/IntelLedger/sawtooth-core.git
   % cd sawtooth-core
   % git checkout 0-7

  Note that the last command switches to the 0.7 branch, which is the version
  covered by this tutorial.

Environment Startup
===================

In order to start the vagrant VM, change the current working directory to
sawtooth-core/tools on the host and run:

.. code-block:: console

  % cd sawtooth-core/tools
  % vagrant up

.. note::

   We have encountered an intermittent problem on Windows hosts which
   presents as an 'Operation not permitted' error in the vagrant startup
   output.  If you encounter this error, perform a 'vagrant destroy' and
   then run 'vagrant up' again.

Downloading the Vagrant box file, booting the VM, and running through
the bootstrap scripts will take several minutes.

Once the 'vagrant up' command has finished executing, run:

.. code-block:: console

  % vagrant ssh

By default, Vagrant sets up ssh keys so that users can log into the VM
without setting up additional accounts or credentials. The logged in user,
vagrant (uid 1000), also has permissions to execute sudo with no password
required. Any number of `vagrant ssh` sessions can be established from the
host.

Resetting the Environment
=========================

If the VM needs to be reset for any reason, it can be returned to the default
state by running the following commands from the sawtooth-core/tools directory
on the host:

.. code-block:: console

  % vagrant destroy
  % vagrant up

.. caution::

   vagrant destroy will delete all contents within the VM. However,
   /vagrant and /project are shared with the host and will be preserved.

Building sawtooth-core
======================

The vagrant environment is setup in such a way that installation of the
software is not required.  However, the C++/swig code must be built.  To
build, run the following inside vagrant:

.. code-block:: console

  $ /project/sawtooth-core/bin/build_all

Running txnvalidator
====================

To start txnvalidator, log in to the development environment with 'vagrant ssh'
and run the following commands:

.. code-block:: console

   $ /project/sawtooth-core/docs/source/tutorial/genesis.sh
   $ cd /project/sawtooth-core
   $ ./bin/txnvalidator -v -F ledger.transaction.integer_key

This will start txnvalidator and logging output will be printed to the
terminal window.

.. note::
  **Note on genesis block creation and clearing validator state**

    The script *genesis.sh* should be run whenever you want to start a
    validator as part of the tutorial. The script clears existing data
    files and keys, which would otherwise be loaded when starting the
    validator. The script also runs a utility that creates a genesis
    block. This utility is part of the sawtooth CLI. To view the available
    subcommands, run the command **sawtooth -h**. The genesis creation
    utility used in this tutorial is: **sawtooth admin poet0-genesis**
    (see script *genesis.sh* for the command line options used in the
    tutorial).


To stop the validator, press CTRL-c.

.. _mktplace-transaction-family-tutorial-label:

Working with the MarketPlace Transaction Family
===============================================

In this section of the tutorial, we will walk though the process of starting
a single validator node and working with mktclient to create users, accounts,
and perform an exchange.

We will setup a couple participants, Alice and Bob, who will exchange goods
(in this case, cookies) for currency (US Dollars).

Start txnvalidator
------------------

By default, the validator is not configured to support the MarketPlace
transaction family or operate efficiently as a single node network. 
The default validator config is in: sawtooth-core/validator/etc/. 

Although you can create a configuration file specifically for the tutorial, 
it is easier to specify the needed options on the command line when starting
the validator.

.. note::
     A configuration file with the MarketPlace transaction family added to the
     default configuration file would like like this:

      .. code-block:: none

          "TransactionFamilies" : [
              "ledger.transaction.integer_key",
              "mktplace.transactions.market_place"
          ],

To test the txnvalidator with the MarketPlace transaction family loaded, run
the following command:

.. code-block:: console

   $ /project/sawtooth-core/docs/source/tutorial/genesis.sh
   $ cd /project/sawtooth-core
   $ ./bin/txnvalidator -v -F mktplace.transactions.market_place

Keep txnvalidator running while we interact with it using mktclient below.
Open a new terminal in your **host** OS and type:

.. code-block:: console

   $ cd $HOME/project/sawtooth-core/tools
   $ vagrant ssh

Key Generation
--------------

First, we need to create key files for each participant that we are going
to use:

  * The Marketplace
  * Alice
  * Bob

Normally these participants may be on different machines talking to different
validators, but for this tutorial we control all the participants, so we
generate a key for each of them:

.. code-block:: console

   $ cd /project/sawtooth-core
   $ ./bin/sawtooth keygen --key-dir validator/keys mkt
   $ ./bin/sawtooth keygen --key-dir validator/keys alice
   $ ./bin/sawtooth keygen --key-dir validator/keys bob


.. _mktplace-object-names-label:

Object Names
------------

Objects within MarketPlace are referenced (named) using paths separated by a
slash (/).  The number of leading slashes determines whether the reference
is an absolute path, a relative path, or an identifier. 

============ =================== =============================================
Count        Format              Description
============ =================== =============================================
Single (/)   /<PATH>             Relative to the current key in use
Double (//)  //<CREATOR>/<PATH>  Fully qualified name
Triple (///) ///<IDENTIFIER>     The object identifier
============ =================== =============================================

In this tutorial, we will stick to the relative paths when possible and specify
absolute paths when referencing objects created by another key (another user).

For example, both Alice and Bob will end up with "/USD" (a relative path), and
the associated absolute paths will be "//bob/USD" and "//alice/USD".

Market Initialization
---------------------

We will use The Marketplace participant (mkt) to setup our example market
so that Alice and Bob can exchange cookies for USD (US dollars).  Bob will
start with a lot of freshly baked cookies and sell them to Alice.

Start mktclient as The Marketplace participant:

.. code-block:: console

   $ cd /project/sawtooth-core
   $ ./bin/mktclient --name mkt --keyfile validator/keys/mkt.wif

Now execute commands as The Marketplace participant (mkt) using the
mktclient shell you just opened.  As you perform these commands, you will
see activity in the txnvalidator output.

To start, let's register the mkt participant, create mkt's account, and
a holding for tokens (a special asset only covered briefly below).

.. code-block:: none

   //UNKNOWN> participant reg --name mkt --description "The Marketplace"
   //mkt> account reg --name /market/account
   //mkt> holding reg --name /market/holding/token --count 1 --account /market/account --asset //marketplace/asset/token

The special token asset is useful for bootstrapping purposes.  Tokens are
non-consumable, in that they are never deducted from a holding even when
exchanged for another asset.  The /market/holding/token as defined has 1 token,
but since it will never be deducted during an exchange, it really has an
infinite number of tokens in practice.  We use it below to create an inital
one-time offer of USD to new participants (an offer which Bob and Alice will
accept later).

Now let's add the currency asset type and USD asset.  Note the count of USD
below is a fixed amount.  By default, asset types are restricted and only the
creator of the asset type can create assets of that type; so here, USD can only
be created by the mkt participant.  The holding will initially contain 20000000
USD.  The sell offer allows new participants to do a one-time exchange for 1000
USD, for the purposes of new participant initialization.

.. code-block:: none

   //mkt> assettype reg --name /asset-type/currency
   //mkt> asset reg --name /asset/currency/USD --type /asset-type/currency
   //mkt> holding reg --name /market/holding/currency/USD --count 20000000 --account /market/account --asset /asset/currency/USD
   //mkt> selloffer reg --name /offer/provision/USD --minimum 1 --maximum 1 --modifier ExecuteOncePerParticipant --output /market/holding/currency/USD --input /market/holding/token --ratio 1 1000

Now that we have USD setup, we need to add the concept of cookies, and
specifically Chocolate Chip cookies, into our blockchain.  To do this, let's
create a cookie asset-type and a Chocolate Chip asset.  If we had different
type of cookies, such as Peanut Butter, we could create additional assets
to represent them.  The cookie asset type is unrestricted, so anyone in the
market place can create cookies.  (Later, Bob will bake a batch.)

.. code-block:: none

   //mkt> assettype reg --name /asset-type/cookie --no-restricted
   //mkt> asset reg --name /asset/cookie/choc_chip --type /asset-type/cookie --no-restricted

The commands above are sent to the validator and applied to the network
asynchronously and may not yet be committed.  You can use the 'waitforcommit'
to have the client block until the changes have been committed:

.. code-block:: none

   //mkt> waitforcommit

.. note::

   :command:`waitforcommit` can potentially take several minutes with a small
   number of validators.  For this section of the tutorial, we are running with
   a single validator and have updated the configuration such that it will
   usually return within a reasonable amount of time.  PoET (the consensus
   mechanism) is optimized for more realistic use cases (not a single
   validator).  The amount of time to wait is related to several factors,
   including a random number mapped to an exponential distribution.  So, if you
   get unlucky, :command:`waitforcommit` might take a while.  As the number of
   validators increases, the average wait time becomes more stable and
   predictable.

Market initialization is complete, so you can now exit mktclient:

.. code-block:: none

   //mkt> exit

Registering Accounts
--------------------

In the previous section, we registered the mkt account.  In this section, we
will register, create accounts, and create initial holdings for both Bob and
Alice.

First, let's register Bob.  Startup mktclient using the name of Bob's key file
(bob):

.. code-block:: console

   $ cd /project/sawtooth-core
   $ ./bin/mktclient --name bob --keyfile validator/keys/bob.wif

Register Bob as a participant and create his account:

.. code-block:: none

   //UNKNOWN> participant reg --name bob
   //bob> account reg --name /account

Now we initialize Bob's USD holding.  We create the USD holding, which will
be empty (Bob can't create USD), and then accept the once-per-particiant
offer from the mkt participant to receive 1000 USD.

.. code-block:: none

   //bob> holding reg --name /USD --account /account --asset //mkt/asset/currency/USD
   //bob> holding reg --name /holding/token --count 1 --account /account --asset //marketplace/asset/token
   //bob> waitforcommit
   //bob> exchange --type SellOffer --src /holding/token --dst /USD --offers //mkt/offer/provision/USD --count 1


Next, let's create an empty cookie jar for Chocolate Chip cookies:

.. code-block:: none

   //bob> holding reg --name /jars/choc_chip --account /account --asset //mkt/asset/cookie/choc_chip

That is it for Bob's setup, so waitforcommit and exit:

.. code-block:: none

   //bob> waitforcommit
   //bob> exit

Now, let's register Alice in the same way.  Startup mktclient using the name of
Alice's key file (alice):

.. code-block:: console

   $ cd /project/sawtooth-core
   $ ./bin/mktclient --name alice --keyfile validator/keys/alice.wif 

Alice's initalization is the same as Bob's:

.. code-block:: none

   //UNKNOWN> participant reg --name alice
   //alice> account reg --name /account
   //alice> holding reg --name /USD --account /account --asset //mkt/asset/currency/USD
   //alice> holding reg --name /holding/token --count 1 --account /account --asset //marketplace/asset/token
   //alice> waitforcommit
   //alice> exchange --type SellOffer --src /holding/token --dst /USD --offers //mkt/offer/provision/USD --count 1
   //alice> holding reg --name /jars/choc_chip --account /account --asset //mkt/asset/cookie/choc_chip
   //alice> waitforcommit
   //alice> exit

Now we have both Alice and Bob's account and holdings initialized.

Create an Exchange Offer
------------------------

Let's assume Bob has baked two dozen Chocolate Chip cookies and wants to create
an exchange offer of $2 per cookie.

Start mktclient with Bob's key:

.. code-block:: console

   $ cd /project/sawtooth-core
   $ ./bin/mktclient --name bob --keyfile validator/keys/bob.wif

Let's create a new holding representing Bob's batch of cookies and initialize
it with 24 cookies.  Then create an exchange offer:

.. code-block:: none

   //bob> holding reg --name /batches/choc_chip001 --account /account --asset //mkt/asset/cookie/choc_chip --count 24
   //bob> exchangeoffer reg --output /batches/choc_chip001 --input /USD --ratio 2 1 --name /choc_chip_sale
   //bob> waitforcommit

Now Bob has two dozen cookies on the market for $2 each.  The ratio argument
says "2 USD for 1 cookie".

View the Bob's current holdings:

.. code-block:: none

   //bob> holdings --creator //bob
   1000     //bob/USD
   24       //bob/batches/choc_chip001
   1        //bob/holding/token
   0        //bob/jars/choc_chip

We can also view Bob's current offers:

.. code-block:: none

   //bob> offers --creator //bob
   Ratio    Input Asset (What You Pay)          Output Asset (What You Get)         Name
   0.5      //mkt/asset/currency/USD            //mkt/asset/cookie/choc_chip        //bob/choc_chip_sale

Great!  Now Bob waits for someone to accept his offer, so we can exit
mktclient:

.. code-block:: none

   //bob> exit

Accept the Exchange Offer
-------------------------

Alice has decided to purchase some cookies and has decided to accept Bob's
exchange offer.

.. code-block:: console

   $ cd /project/sawtooth-core
   $ ./bin/mktclient --name alice --keyfile validator/keys/alice.wif

Execute an exchange (accepting Bob's offer):

.. code-block:: none

   //alice> exchange --type ExchangeOffer --src /USD --dst /jars/choc_chip --offers //bob/choc_chip_sale --count 24
   //alice> waitforcommit

The count above is related to the --src argument, so 24 USD for a dozen
cookies.  Let's see what the resulting holdings look like:

.. code-block:: none

   //alice> holdings --creator //bob
   1024     //bob/USD
   12       //bob/batches/choc_chip001
   1        //bob/holding/token
   0        //bob/jars/choc_chip
   //alice> holdings --creator //alice
   976      //alice/USD
   1        //alice/holding/token
   12       //alice/jars/choc_chip

Fantastic!  Bob has more USD and fewer cookies.  Alice has less USD and more
cookies.

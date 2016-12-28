***************************
Transaction Family Tutorial
***************************

Overview
========

This tutorial covers the creation of a new Sawtooth Lake transaction family.
We will construct a transaction family called 'sawtooth_xo' which implements
a distributed version of the multi-player game tic-tac-toe.

A general description of tic-tac-toe, including the rules, can be found on
Wikipedia at:

    https://en.wikipedia.org/wiki/Tic-tac-toe

Prerequisites
=============

This tutorial assumes that you have gone through the primary Sawtooth Lake
:doc:`tutorial` and are familiar with the concepts introduced there.

Prior to going through this tutorial, you should have a working vagrant
environment running to which you can login.  Specific setup instructions
are available in the :doc:`tutorial`.

Transaction Family Tutorial Sample Code
=======================================

In this tutorial, we use example code defined in the **txn_family_tutorial**
directory of the documentation to allow you to step through the tutorial without
manually entering any code.  At each step, you can review the code for that step
before proceeding to the next step.  The code examples are located in subfolders
named using the convention *xo-tutorial-stepNN*, where NN is a two-digit number.
You simply source a special script named *env.sh* before you run the code for each
step. The script **env.sh** sets the PYTHONPATH environment variable to the
correct value, so that the python  interpreter knows which code examples to run,
when you  start the validator.


A complete implementation, along with other example transaction families,
is also available in master branch of sawtooth-core.

The repository is located at:

    https://github.com/hyperledger/sawtooth-core

The example transaction families are located at:

    https://github.com/hyperledger/sawtooth-core/tree/master/extensions/arcade

Instructions for what to do with the repo are in the next section.

Change to the Correct Working Directory for Tutorial Start
==========================================================

From following the Sawtooth Lake Tutorial, you should already have cloned the
following repository:

.. code-block:: console

    project/
      sawtooth-core/

You already have the transaction family tutorial code in your repository, in the
directory ``/project/sawtooth-core/docs/source/txn_family_tutorial``. 

Change your working directory to the **xo-tutorial-step00** subdirectory:

.. code-block:: console

    % cd /project/sawtooth-core/docs/source/txn_family_tutorial/xo-tutorial-step00

There will only be one file in the ``xo-tutorial-step00`` directory: README.md 

.. code-block:: console

    % ls
    README.md

Please read the README.md file now with your favorite text editor.

Components
==========

As messages containing transactions are received by a validator, they are
validated and applied to the local state of the validator.  The transaction
family defines the message type and the business logic used for validation
and state changes.

There are three top-level components of a transaction family:

- a registration function
- a message class
- a transaction class

txnvalidator Configuration and Dynamic Loading
==============================================

txnvalidator dynamically loads transaction families based on the
"TransactionFamilies" setting in the txnvalidator.js configuration file.  As
the validator processes the list, it loads each transaction family's Python
module and calls the function 'register_transaction_types' as defined in
that module.

To enable sawtooth_xo, the txnvalidator.js configuration must include
sawtooth_xo in the "TransactionFamilies" list:

.. code-block:: none

    "TransactionFamilies" : [
        "sawtooth_xo"
    ],

Observe that in txnvalidator.js, sawtooth_xo is listed as the only transaction
family. This will load the sawtooth_xo python module and run 
sawtooth_xo.register_transaction_types.

You can also have more than one transaction family configured at once:

.. code-block:: none

    "TransactionFamilies" : [
        "ledger.transaction.integer_key",
        "sawtooth_xo"
    ],

In this case, the validator iterates over the list and registers one at a
time.

At this time, change your working directory to the **xo-tutorial-step01**
directory, then source the **env.sh** script:

.. code-block:: console

    % cd /project/sawtooth-core/docs/source/txn_family_tutorial/xo-tutorial-step01
    % source env.sh

Two new files have been added for this step:

.. code-block:: console
    
    xo-tutorial-step01/sawtooth_xo/__init__.py
    xo-tutorial-step01/sawtooth_xo/txn_family.py

In sawtooth_xo/__init__.py, register_transaction_types is defined as:

*sawtooth_xo/__init__.py*

.. code-block:: python

    from sawtooth_xo.txn_family import _register_transaction_types

    def register_transaction_types(journal):
        _register_transaction_types(journal)

Thus, although the starting point is the sawtooth_xo module's __init__.py, we
have chosen to keep the implementation in the sawtooth_xo.txn_family module.
This is purely to keep the transaction family name listed in txnvalidator.js
as short and simple as possible: 'sawtooth_xo'.

In sawtooth_xo/txn_family.py, we now have a register function which logs an
error - it doesn't register anything quite yet.

Inside the vagrant environment, in the same terminal window you used to source the
special script *env.sh* above, start a txnvalidator as follows, and after a few
seconds, kill it by pressing CTRL-C:

.. code-block:: console

    $ cd /project/sawtooth-core
    $ ./docs/source/txn_family_tutorial/genesis.sh
    $ ./bin/txnvalidator -v --config /project/sawtooth-core/docs/source/txn_family_tutorial/txnvalidator.js

    ...
    [02:51:45 INFO    validator_cli] adding transaction family: sawtooth_xo
    [02:51:45 ERROR   txn_family] sawtooth_xo register_transaction_types not implemented
    ...
    <CTRL-C>

Observe the INFO and ERROR lines above.  The first is printed by the
validator prior to attempting to load the transaction family.  This is a
quick way to determine if your transaction family is being loaded.  The
next line is the error logging message we have as the current implementation
of sawtooth_xo.txn_family.register_transaction_types().

Skeleton Implementation
=======================

Now, change your working directory to the **xo-tutorial-step02** subdirectory,
then source the **env.sh** script:

.. code-block:: console

    % cd /project/sawtooth-core/docs/source/txn_family_tutorial/xo-tutorial-step02
    % source env.sh

This updates sawtooth_xo/txn_family.py such that it contains all the framework
of the transaction family, but several methods are not yet implemented.
Let's look at this initial skeleton code.

Registration
------------

The implementation of _register_transaction_types, which is now complete,
looks like this:

*sawtooth_xo/txn_family.py*

.. code-block:: python

    from journal.messages import transaction_message

    def _register_transaction_types(journal):
        journal.register_message_handler(
            XoTransactionMessage,
            transaction_message.transaction_message_handler)
        journal.add_transaction_store(XoTransaction)

The journal object being passed into this function is a type derived from
journal.journal_core.Journal from `sawtooth-core <http://github.com/HyperLedger/sawtooth-core>`__
(such as PoetJournal).  We
register the standard transaction message handler to
specify the message type of XoTransactionMessage, which is derived from
transaction_message.TransactionMessage.

Lastly, we add the transaction store. The method add_transaction_store() takes the
transaction type as input (XoTransaction).  It adds an instance of the
appropriate store type to the global store, using the transaction type's
name.

The Message Class
-----------------

The implementation of XoTransactionMessage, which is also complete:

*sawtooth_xo/txn_family.py*

.. code-block:: python

    from journal.messages import transaction_message

    class XoTransactionMessage(transaction_message.TransactionMessage):
        MessageType = "/Xo/Transaction"

        def __init__(self, minfo=None):
            if minfo is None:
                minfo = {}

            super(XoTransactionMessage, self).__init__(minfo)

            tinfo = minfo.get('Transaction', {})
            self.Transaction = XoTransaction(tinfo)


Most of the work is done by the TransactionMessage, so our derived class
is fairly simple.

The MessageType class attribute specifies the name used for these types of
messages.  This is used in several places; for example, it is used when
correlating message statistics.

During __init__, the minfo argument is used for deserialization.  It is used by
the implementation in this class and the base classes to restore an object.  In
this implementation, it uses it to restore a XoTransaction instance (if
'Transaction' is set in minfo) by passing tinfo to XoTransaction's constructor.

The Transaction Class
---------------------

The transaction class is the heart of a transaction family.  It must define:

- TransactionTypeName class attribute
- TransactionStoreType class attribute
- MessageType class attribute
- An __init__() method which implements deserialization
- A __str__() method
- A check_valid() method which throws an exception if the transaction is not valid
- An apply() method which updates the store
- A dump() method which implements serialization

The skeleton implementation is:

*sawtooth_xo/txn_family.py*

.. code-block:: python

    class XoTransaction(transaction.Transaction):
        TransactionTypeName = '/XoTransaction'
        TransactionStoreType = global_store_manager.KeyValueStore
        MessageType = XoTransactionMessage

        def __init__(self, minfo=None):
            if minfo is None:
                minfo = {}

            super(XoTransaction, self).__init__(minfo)

            LOGGER.debug("minfo: %s", repr(minfo))
            LOGGER.error("XoTransaction __init__ not implemented")

        def __str__(self):
            LOGGER.error("XoTransaction __str__ not implemented")
            return "XoTransaction"

        def check_valid(self, store):

            super(XoTransaction, self).check_valid(store)

            LOGGER.debug('checking %s', str(self))

            raise InvalidTransactionError('XoTransaction.check_valid is not implemented')

        def apply(self, store):
            LOGGER.debug('apply %s', str(self))
            LOGGER.error('XoTransaction.apply is not implemented')

        def dump(self):
            result = super(XoTransaction, self).dump()

            LOGGER.error('XoTransaction.dump is not implemented')

            return result


CLI Client
==========

Before we move forward with implementation, we need an easy way to submit
transactions to a validator.  We also need a way to view the current state
of the store (which in this case, will be game state).

Describing the CLI client in detail is out-of-scope for this tutorial, but
we will point out a few important pieces.

At this time, change your working directory to the **xo-tutorial-step03** directory,
then source the **env.sh** script:

.. code-block:: console

    % cd /project/sawtooth-core/docs/source/txn_family_tutorial/xo-tutorial-step03
    % source env.sh

Three new files have been added:

.. code-block:: none

    xo-tutorial-step03/bin/xo
    xo-tutorial-step03/sawtooth-xo/xo_cli.py
    xo-tutorial-step03/sawtooth-xo/xo_client.py

bin/xo is a small script which launches the CLI code contained in xo_cli.py.
We will not dive deep into the implementation of the CLI itself; it is fairly
straight-forward argparse code.  However, we will use it extensively to
submit transactions and web API requests to the validator.

xo_client.py contains an implementation of XoClient, which is derived from
SawtoothClient.  The SawtoothClient base class takes care of all of the
details related to submitting transactions and retrieving state.  XoClient
provides a couple methods for creating transactions:

*sawtooth_xo/xo_client.py*

.. code-block:: python

    def send_xo_txn(self, update):
        """
        This sets up the same defaults as the Transaction so when
        signing happens in sendtxn, the same payload is signed.
        Args:
            update: dict The data associated with the Xo data model
        Returns:
            txnid: str The txnid associated with the transaction

        """
        if 'Name' not in update:
            update['Name'] = None
        if 'Action' not in update:
            update['Action'] = None
        if 'Space' in update and update['Space'] is None:
            del update['Space']
        return self.sendtxn('/XoTransaction',
                            '/Xo/Transaction',
                            update)

    def create(self, name):
        """
        """
        update = {
            'Action': 'CREATE',
            'Name': name
        }

        return self.send_xo_txn(update)

    def take(self, name, space):
        """
        """
        update = {
            'Action': 'TAKE',
            'Name': name,
            'Space': space,
        }
        return self.send_xo_txn(update)

In both cases, an XoTransaction is sent (wrapped in a XoTransactionMessage),
but the update has different actions.  The two allowable actions for
our tic-tac-toe implementation are CREATE and TAKE.  CREATE takes the name
of the game to create, and TAKE takes the name of the game and the space.  We
imply all other implementation from the state of the transaction family's
store.

Another thing to note is that XoClient is aware of the XoTransaction
family and will run check_valid() and apply() locally prior to sending
the transaction to the validator.  This allows the CLI client to catch
obvious errors prior to submitting them as a transaction.

Let's submit a transaction and see the result.

First, startup txnvaldiator inside vagrant (and leave it running):

.. note:: Start the txnvalidator in the same terminal window in which you 
          sourced the **env.sh** script, or run the following command from a 
          new vagrant window (log in with "vagrant ssh"):

          .. code-block:: console

            $ source /project/sawtooth-core/docs/source/txn_family_tutorial/xo-tutorial-step03/env.sh

Run the following commands to start the validator:

.. code-block:: console

    $ cd /project/sawtooth-core
    $ ./docs/source/txn_family_tutorial/genesis.sh
    $ ./bin/txnvalidator -v --config /project/sawtooth-core/docs/source/txn_family_tutorial/txnvalidator.js


Next, in a separate vagrant window, use the xo CLI to create a key for player1:

.. code-block:: console

    % source /project/sawtooth-core/docs/source/txn_family_tutorial/xo-tutorial-step03/env.sh
    $ cd /project/sawtooth-core
    $ ./bin/xo init --username=player1

Then, attempt to create a game:

.. code-block:: console

    $ ./bin/xo create -vvv game000
    [15:40:54 DEBUG   client] set signing key from file /home/vagrant/.sawtooth/keys/player1.wif
    [15:40:54 DEBUG   client] Posting transaction: 77b85773bbb5a3d0
    ?iSignaturexXHIkL44U02V3SfohF6KjVA3xvxbIwWpGsxehOiKyhOWEaCtchVgGGe5jmlQrJ6ASEW8vxOyKbkOllC4lmimFVlYw=oTransactionTypen/XoTransactioni__NONCE__?A???y:m__SIGNATURE__xXGwHRqQG0gMaqp3qOC944bveycd+n5cSrGez32NtN6TO7wMGpnJnONCNQ0ImJo4+l1r91iI0tQ1CprFxZPzWat/k=h__TYPE__o/Xo/Transaction>
    [15:40:54 WARNING client] operation failed with response: 400 OrderedDict([('error', 'XoTransaction.check_valid is not implemented'), ('errorType', 'InvalidTransactionError'), ('status', 400L)])
    Error: XoTransaction.check_valid is not implemented

Stop the validator with CTRL-C.

Great! The client fetched the state (which will have been empty, but note the
URL, that's our store), created a signed transaction, then ran check_valid.
Since we throw an exception in check_valid, we got the expected error message.

Now we are ready to complete the rest of the implementation.

Serialization and Deserialization
=================================

At this time, change your working directory to the **xo-tutorial-step04** directory:

.. code-block:: console

    % cd /project/sawtooth-core/docs/source/txn_family_tutorial/xo-tutorial-step04

As we saw in the client section, we have two possible actions: CREATE and TAKE.
CREATE requires a name, and TAKE requires a name and a space.  So we have three
fields that make up a transaction: Action, Name, and Space.

The __init__() implementation restores these fields from minfo if they are
present there during construction:

*sawtooth_xo/txn_family.py*

.. code-block:: python

    class XoTransaction(transaction.Transaction):
        def __init__(self, minfo=None):
            if minfo is None:
                minfo = {}

            super(XoTransaction, self).__init__(minfo)

            LOGGER.debug("minfo: %s", repr(minfo))
            self._name = minfo['Name'] if 'Name' in minfo else None
            self._action = minfo['Action'] if 'Action' in minfo else None
            self._space = minfo['Space'] if 'Space' in minfo else None

If they are not specified in minfo, they default to None.

The dump() method does the reverse and serializes the data:

*sawtooth_xo/txn_family.py*

.. code-block:: python

    def dump(self):
        result = super(XoTransaction, self).dump()

        result['Action'] = self._action
        result['Name'] = self._name
        if self._space is not None:
            result['Space'] = self._space

        return result

Note that the implementation of __init__() and dump() define the structure of
the transaction data.  Both of these methods call their base classes.  The base
classes will add/restore additional fields to the transaction.

We can now also implement __str__() since all the relevant fields are defined:

*sawtooth_xo/txn_family.py*

.. code-block:: python

    def __str__(self):
        try:
            oid = self.OriginatorID
        except AssertionError:
            oid = "unknown"
        return "({0} {1} {2})".format(oid,
                                      self._name,
                                      self._space)


Implementing apply() and check_valid()
======================================

The check_valid() method throws an XoException if the transaction can not be
applied for some reason.  For example, it will throw an exception if, during
a CREATE, a game name is already in use.

The apply() method takes the transaction's data and modifies the store in
the appropriate way.  It assumes that check_valid() has been called just
before, in that it does not re-check everything checked with check_valid().

The implementation of check_valid():

*sawtooth_xo/txn_family.py*

.. code-block:: python

    def check_valid(self, store):
        super(XoTransaction, self).check_valid(store)

        LOGGER.debug('checking %s', str(self))

        if self._name is None or self._name == '':
            raise InvalidTransactionError('name not set')

        if self._action is None or self._action == '':
            raise InvalidTransactionError('action not set')

        if self._action == 'CREATE':
            if self._name in store:
                raise InvalidTransactionError('game already exists')
        elif self._action == 'TAKE':
            if self._space is None:
                raise InvalidTransactionError('TAKE requires space')

            if self._space < 1 or self._space > 9:
                raise InvalidTransactionError('invalid space')

            if self._name not in store:
                raise InvalidTransactionError('no such game')

            state = store[self._name]['State']
            if state in ['P1-WIN', 'P2-WIN', 'TIE']:
                raise InvalidTransactionError('game complete')

            if state == 'P1-NEXT' and 'Player1' in store[self._name]:
                player1 = store[self._name]['Player1']
                if player1 != self.OriginatorID:
                    raise InvalidTransactionError('invalid player 1')

            if state == 'P2-NEXT' and 'Player2' in store[self._name]:
                player1 = store[self._name]['Player2']
                if player1 != self.OriginatorID:
                    raise InvalidTransactionError('invalid player 2')

            if store[self._name]['Board'][self._space - 1] != '-':
                raise InvalidTransactionError('space already taken')
        else:
            raise InvalidTransactionError('invalid action')

The implementation of apply():

.. code-block:: python

    def apply(self, store):
        LOGGER.debug('apply %s', str(self))

        if self._name in store:
            game = store[self._name].copy()
        else:
            game = {}

        if 'Board' in game:
            board = list(game['Board'])
        else:
            board = list('---------')
            state = 'P1-NEXT'

        if self._space is not None:
            if board.count('X') > board.count('O'):
                board[self._space - 1] = 'O'
                state = 'P1-NEXT'
            else:
                board[self._space - 1] = 'X'
                state = 'P2-NEXT'

            # The first time a space is taken, player 1 will be assigned.  The
            # second time a space is taken, player 2 will be assigned.
            if 'Player1' not in game:
                game['Player1'] = self.OriginatorID
            elif 'Player2' not in game:
                game['Player2'] = self.OriginatorID

        game['Board'] = "".join(board)
        if self._is_win(game['Board'], 'X'):
            state = 'P1-WIN'
        elif self._is_win(game['Board'], 'O'):
            state = 'P2-WIN'
        elif '-' not in game['Board']:
            state = 'TIE'

        game['State'] = state
        store[self._name] = game

The implementation of apply() uses _is_win():

.. code-block:: python

    def _is_win(self, board, letter):
        wins = ((1, 2, 3), (4, 5, 6), (7, 8, 9),
                (1, 4, 7), (2, 5, 8), (3, 6, 9),
                (1, 5, 9), (3, 5, 7))

        for win in wins:
            if (board[win[0] - 1] == letter
                    and board[win[1] - 1] == letter
                    and board[win[2] - 1] == letter):
                return True

        return False

It is now possible to play the game:

.. code-block:: console

    $ source /project/sawtooth-core/docs/source/txn_family_tutorial/xo-tutorial-step04/env.sh
    $ cd /project/sawtooth-core
    $ ./docs/source/txn_family_tutorial/genesis.sh
    $ ./bin/txnvalidator -v --config /project/sawtooth-core/docs/source/txn_family_tutorial/txnvalidator.js


Then, create a game in a separate vagrant window (log in with "vagrant ssh" from the tools directory):

.. code-block:: console

    $ source /project/sawtooth-core/docs/source/txn_family_tutorial/xo-tutorial-step04/env.sh
    $ cd /project/sawtooth-core
    $ ./bin/xo create -vvv game001 --wait
    [04:53:07 DEBUG   client] fetch state from http://localhost:8800/XoTransaction/*
    [04:53:07 DEBUG   client] get content from url <http://localhost:8800/store/XoTransaction/\*>
    [04:53:07 DEBUG   client] set signing key from file /home/vagrant/.sawtooth/keys/player1.wif
    [04:53:07 DEBUG   txn_family] minfo: {'Action': 'CREATE', 'Name': 'game001'}
    [04:53:07 DEBUG   txn_family] checking (1NNxoo58EsR5cCEACiJf9mvoVLrGF37kvV game001 None)
    [04:53:07 DEBUG   txn_family] minfo: {}
    [04:53:07 DEBUG   client] Posting transaction: 12e8a91cb8dcd0fc
    [04:53:07 DEBUG   client] post transaction to http://localhost:8800/Xo/Transaction with DATALEN=349, DATA=<?kTransaction?fActionfCREATElDependencies?dNameggame002eNonce?A??7??7?iSignaturexXHIosnrTVbfgUL2jAc13I2i3H9/bEZ5l6/VGx0W4/H0Sh9BCmwDmku7bsApz3ykfwYr9yEiLprS0fL1YztqOzXqk=oTransactionTypen/XoTransactioni__NONCE__?A??7??Sm__SIGNATURE__xXHC5nsdONidVTX4ond7zOJgXvXOOvkQl5DYRNh1MglAEPSMK5NCDKViUfnuaTjIWyTFRLKTpsqatdBIJEghMXVJE=h__TYPE__o/Xo/Transaction>
    [04:53:07 DEBUG   client] {
      "Transaction": {
        "Action": "CREATE",
        "Dependencies": [],
        "Name": "game001",
        "Nonce": 1465966387.019018,
        "Signature": "HIosnrTVbfgUL2jAc13I2i3H9/bEZ5l6/VGx0W4/H0Sh9BCmwDmku7bsApz3ykfwYr9yEiLprS0fL1YztqOzXqk=",
        "TransactionType": "/XoTransaction"
      },
      "__NONCE__": 1465966387.031697,
      "__SIGNATURE__": "HC5nsdONidVTX4ond7zOJgXvXOOvkQl5DYRNh1MglAEPSMK5NCDKViUfnuaTjIWyTFRLKTpsqatdBIJEghMXVJE=",
      "__TYPE__": "/Xo/Transaction"
    }
    [04:53:07 DEBUG   txn_family] apply (1NNxoo58EsR5cCEACiJf9mvoVLrGF37kvV game001 None)
    [04:53:07 DEBUG   client] get content from url <http://localhost:8800/transaction/12e8a91cb8dcd0fc>
    [04:53:07 DEBUG   client] waiting for transaction 12e8a91cb8dcd0fc to commit
    [04:53:12 DEBUG   client] get content from url <http://localhost:8800/transaction/12e8a91cb8dcd0fc>
    [04:53:12 DEBUG   client] waiting for transaction 12e8a91cb8dcd0fc to commit
    [04:53:17 DEBUG   client] get content from url <http://localhost:8800/transaction/12e8a91cb8dcd0fc>
    [04:53:17 DEBUG   client] waiting for transaction 12e8a91cb8dcd0fc to commit
    [04:53:22 DEBUG   client] get content from url <http://localhost:8800/transaction/12e8a91cb8dcd0fc>
    [04:53:22 DEBUG   client] waiting for transaction 12e8a91cb8dcd0fc to commit
    [04:53:27 DEBUG   client] get content from url <http://localhost:8800/transaction/12e8a91cb8dcd0fc>
    [04:53:27 DEBUG   client] waiting for transaction 12e8a91cb8dcd0fc to commit
    [04:53:32 DEBUG   client] get content from url <http://localhost:8800/transaction/12e8a91cb8dcd0fc>

The xo CLI also has a take subcommand for taking a space, a list subcommand for
viewing the list of games, and a show subcommand for showing the board of a
specific game.


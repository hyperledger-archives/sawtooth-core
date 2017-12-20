*****************************************
Introduction to the XO Transaction Family
*****************************************

What is XO?
===========

*XO* is an example transaction family contained within the Sawtooth SDK. It is an
implementation of the popular game *Tic-tac-toe* (otherwise known as
*Noughts and Crosses* or *X's and O's*).

*X's and O's*-style games have been played across the world for many centuries. The
origin of this type of game is unclear; however, some historians believe that the first
version of *Tic-tac-toe* may have originated in ancient Egypt. Others believe that the
modern *Tic-tac-toe* is an evolution of a game known as *Terni Lapilli*, which was
popular within the Roman Empire.

*Tic-tac-toe* also has historical significance within the field of Computer Science. In
1952, it became the basis of one of the first-ever video games when
`OXO <https://en.wikipedia.org/wiki/OXO>`_ was developed by Alexander S. Douglas at the
University of Cambridge. More information regarding the origins and properties of
*Tic-tac-toe* can be found `here <https://en.wikipedia.org/wiki/Tic-tac-toe>`_.

*XO* was chosen as an example transaction family for Sawtooth due to its simplicity,
global player base, and straightforward implementation as a computer program. This example
transaction family demonstrates the functionality of Sawtooth, and the code that implements
it serves as a reference for building other transaction processors.

How to Play XO
==============

Game Rules
----------

*Tic-tac-toe* is a two-player game in which players take turns marking spaces on a 3x3
grid. Conventionally, *player one* marks spaces with an 'X' and *player two* marks spaces
with an 'O'; and *player one* always takes the first turn.

A player wins the game by marking 3 spaces in a horizontal, vertical, or diagonal row.
If all 9 spaces on the grid have been marked but no player has achieved a winning board
position, the game is considered a draw.

Playing XO Using the Command-line Interface
-------------------------------------------

A command-line interface is provided for playing *XO* which handles the construction and
submission of transactions. Instructions on how to use the CLI are detailed below:

Start up a validator, *XO* transaction processor, and the REST API. For more information
on configuring and running Sawtooth components, see
:doc:`/app_developers_guide/installing_sawtooth`.

A user creates a new game using the ``xo create [name]`` command.

- The *name* argument is the identifier for the new game to be created.

Players take turns using the ``xo take [name] [space]`` command to mark spaces on
the grid.

- The *name* argument is the identifier for an existing game.
- The *space* argument is the space that is to be marked, which is an integer in the
  range of 1 through 9.

.. note::

  The first player to issue an ``xo take`` command to a newly created game is
  recorded by their username as *player one*. The second player to issue a ``take``
  command is recorded by their username as *player two*.

``xo create`` and ``xo take`` each take ``--username`` and
``--key-dir`` arguments. These are used to locate the user's private
key file: ``<key-dir>/<username>.priv``. ``key-dir`` defaults to
``~/.sawtooth/keys`` and ``username`` defaults to the name of the OS
user.

.. note::

  All ``xo`` commands also support ``--auth-user`` and ``--auth-password``,
  but these options are not used in this example.

Each time a user attempts to take a space, the transaction processor will verify
that their username matches the name of the player whose turn it is. This ensures
that no player is able to mark a space out of turn.

The *XO* transaction processor will scan for winning or draw board conditions after
each turn. If either condition occurs, further ``take`` actions on the finished game
will not be allowed.

.. note::

  Either user can use the ``xo reset`` command to delete their local *XO* data.
  This includes the saved URL and username.

Viewing the Game State
----------------------

The *XO* CLI also supports commands to view the state of ongoing or finished games.
These commands are ``xo show [game]`` and ``xo list``

- ``xo show [game]`` shows the board of a specified game, as well as data about the
  players and game state.
- ``xo list`` shows a list of all ongoing and finished games.

.. note::

  The *XO* client optionally supports authentication. If the REST API
  is connected to an authentication proxy, you can point the *XO*
  client at it with the ``--url`` argument. You must enter your
  authentication information using the ``--auth-user [user]`` and
  ``--auth-password [password]`` options for each *XO* command.

  *Note that the value of the* ``--auth-user`` *argument is not the
  same username that is entered with the* ``--username`` *argument*.

URL
---

The ``xo`` commands all take a ``--url`` argument that defaults to
``http://127.0.0.1:8008``. This should be set to the URL of the REST
API. The *XO* client will send requests to update and query the
blockchain to this URL.


.. seealso::
  :doc:`/cli/xo`

Playing XO with the XO Client (Example)
=======================================

Now that we have gone through the basics of the *XO* transaction processor, we are ready
to play a game. The steps below show you how to set up and play a game using the *XO* CLI.

Start the Necessary Components
------------------------------

To play *XO*, ensure that the following components are running and connected:

#. At least one validator
#. An *XO* family transaction processor
#. The REST API

Create Players
--------------

Create keys for two players to play the game:

.. code-block:: console

    $ sawtooth keygen jack
    $ sawtooth keygen jill


The command produces output similar to the following for both players:

.. code-block:: console

    writing file: /home/ubuntu/.sawtooth/keys/jack.priv
    writing file: /home/ubuntu/.sawtooth/keys/jack.addr
    writing file: /home/ubuntu/.sawtooth/keys/jill.priv
    writing file: /home/ubuntu/.sawtooth/keys/jill.addr


Create a Game
-------------

Create a game with the following command:

.. code-block:: console

    $ xo create game --username jack

To see list of the created games, enter the following command:

.. code-block:: console

    $ xo list

The command outputs a list of the games that have been created:

.. code-block:: console

    GAME            PLAYER 1        PLAYER 2        BOARD     STATE
    game                                            --------- P1-NEXT


Take a Space as Player One
--------------------------

Start playing by taking a space as the first player, "jack":

.. code-block:: console

    $ xo take game 5 --username jack

.. note::

    The board spaces are numbered from 1 to 9. The upper-left corner is
    number 1, and the lower right corner is number 9.


Take a Space as Player Two
--------------------------

Now take a space on the board as player two:

.. code-block:: console

    $ xo take game 1 --username jill


Show the Current State of the Game Board
----------------------------------------

Whenever you want to see the current state of the game board, enter the
following command:

.. code-block:: console

    $ xo show game

You will see the current state of the board displayed:

.. code-block:: console

    GAME:     : game
    PLAYER 1  : 02403a
    PLAYER 2  : 03729b
    STATE     : P1-NEXT

      O |   |
     ---|---|---
        | X |
     ---|---|---
        |   |


Continue the Game
-----------------

You can continue the game until one of the players wins, or
the game ends in a draw:

.. code-block:: console

    $ xo show game
    GAME:     : game
    PLAYER 1  : 02403a
    PLAYER 2  : 03729b
    STATE     : TIE

      O | X | O
     ---|---|---
      X | X | O
     ---|---|---
      X | O | X


XO Transaction Family Specification
===================================

The XO Transaction Family Specification contains technical information about the *XO*
transaction family. This specification can be found here:
:doc:`/transaction_family_specifications/xo_transaction_family`

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

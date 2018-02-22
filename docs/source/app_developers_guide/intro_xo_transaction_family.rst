*****************************************
Introduction to the XO Transaction Family
*****************************************

XO is an example transaction family that implements the game
`tic-tac-toe <https://en.wikipedia.org/wiki/Tic-tac-toe>`_,
also known as *Noughts and Crosses* or *X's and O's*.
We chose XO as an example transaction family for Sawtooth because of its
simplicity, global player base, and straightforward implementation as a computer
program. This transaction family demonstrates the functionality of Sawtooth;
in addition, the code that implements it serves as a reference for building
other transaction processors.

This section introduces the concepts of a Sawtooth transaction family with XO,
summarizes XO game rules, and describes how use the ``xo`` client application
to play a game of tic-tac-toe on the blockchain.


About the XO Transaction Family
===============================

The XO transaction family defines the data model and business logic for
playing tic-tac-toe on the blockchain by submitting transactions for `create`,
`take`, and `delete` actions. For more information, see
:doc:`/transaction_family_specifications/xo_transaction_family`

The XO transaction family includes:

 * Transaction processors in several languages, including Go (``xo-tp-go``),
   JavaScript (``xo-tp-js``), and Python (``xo-tp-python``). These transaction
   processors implement the business logic of XO game play.

 * An ``xo`` client: A set of commands that provide a command-line interface
   for playing XO. The ``xo`` client handles the constructing and submission
   of transactions. For more information, see :doc:`/cli/xo`.


Game Rules
==========

In tic-tac-toe, two players take turns marking spaces on a 3x3 grid.

* The first player (player 1) marks spaces with an X. Player 1 always
  makes the first move.

* The second player (player 2) marks spaces with an O.

* A player wins the game by marking three adjoining spaces in a horizontal,
  vertical, or diagonal row.

* The game is a tie if all nine spaces on the grid have been marked,
  but no player has won.

See `Wikipedia <https://en.wikipedia.org/wiki/Tic-tac-toe>`_ for more
information on playing tic-tac-toe.
For the detailed business logic of game play, see "Execution" in
:doc:`/transaction_family_specifications/xo_transaction_family`.


Playing XO with the xo Client
=============================

This procedure introduces you to the XO transaction family by playing a game
with the ``xo`` client.


Prerequisites
-------------

* A working Sawtooth development environment, as described in
  :doc:`/app_developers_guide/installing_sawtooth`.
  Ensure that this environment is running a validator, a REST API, and an XO
  transaction processor (such as ``xo-tp-python``).

* If you are using a Docker development environment, open a client container
  by running the following command from your host computer’s terminal window:

  .. code-block:: console

     % docker exec -it sawtooth-shell-default bash

* Verify that you can connect to the REST API.

  * Docker: See :ref:`confirming-connectivity-docker-label`

  * Ubuntu: See :doc:`/app_developers_guide/installing_sawtooth`

  * AWS: See :ref:`confirming-connectivity-aws-label`

  .. Important::

     The ``xo`` client sends requests to update and query the blockchain to the
     URL of the REST API (by default, ``http://127.0.0.1:8008``).

     If the REST API's URL is not ``http://127.0.0.1:8008``, you must add the
     ``--url`` argument to each ``xo`` command in this procedure.


Step 1. Create Players
----------------------

Create keys for two players to play the game:

.. code-block:: console

    $ sawtooth keygen jack
    writing file: /home/ubuntu/.sawtooth/keys/jack.priv
    writing file: /home/ubuntu/.sawtooth/keys/jack.addr

    $ sawtooth keygen jill
    writing file: /home/ubuntu/.sawtooth/keys/jill.priv
    writing file: /home/ubuntu/.sawtooth/keys/jill.addr


.. note::

   The output may differ slightly from this example.


Step 2. Create a Game
---------------------

Create a game named ``game`` with the following command:

.. code-block:: console

    $ xo create game --username jack

To specify a non-default URL for the REST API, add the ``url`` argument
to this and all following ``xo`` commands.  This example shows the URL for
the Docker application environment, ``http://rest-api:8008``.

.. code-block:: console

   $ xo create game --username jack --url http://rest-api:8008

.. note::

   The ``--username`` argument is required for ``xo create`` and ``xo take``
   so that a single user (you) can play as two players. By default,
   ``<username>`` is the player's user name.

   An optional ``--key-dir`` argument can be used to specify a non-default
   location for the user's private key file. By default, this file is at
   ``<key-dir>/<username>.priv``.

Verify that the game was created by displaying the list of existing games:

.. code-block:: console

    $ xo list
    GAME            PLAYER 1        PLAYER 2        BOARD     STATE
    game                                            --------- P1-NEXT


Step 3. Take a Space as Player 1
--------------------------------

The first player to issue an ``xo take`` command to a newly created game is
recorded by username as ``PLAYER 1``. The second player to issue a ``take``
command is recorded by username as ``PLAYER 2``.

Start playing tic-tac-toe by taking a space as the first player, Jack. In this
example, Jack takes space 5:

.. code-block:: console

    $ xo take game 5 --username jack

.. note::

    The board spaces are numbered from 1 to 9. The upper-left corner is
    number 1, and the lower right corner is number 9. This example shows
    the number of each space.

     .. code-block:: none

        1 | 2 | 3
       ---|---|---
        4 | 5 | 6
       ---|---|---
        7 | 8 | 9


Step 4. Take a Space as Player 2
--------------------------------

Next, take a space on the board as player 2, Jill.  In this example,
Jill takes space 1:

.. code-block:: console

    $ xo take game 1 --username jill


Step 5. Show the Current Game Board
-----------------------------------

Whenever you want to see the current state of the game board, enter the
following command:

.. code-block:: console

    $ xo show game

The output includes the game name, public key of each player, game state,
and the current board state. This example shows the game state ``P1-NEXT``
(player 1 has the next turn) and a board with Jack's X in space 5 (the center)
and Jill's 0 in space 1 (the upper left).

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


Step 6. Continue the Game
-------------------------

Players take turns using ``xo take <name> <space>`` to mark spaces on the grid.

Each time a user attempts to take a space, the transaction processor will verify
that their username matches the name of the player whose turn it is. This
ensures that no player is able to mark a space out of turn.

After each turn, the XO transaction processor scans the board state for a win or
tie. If either condition occurs, no more ``take`` actions are allowed on the
finished game.

You can continue the game until one of the players wins or the game ends in a
tie, as in this example:

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


Step 7. Delete the Game
-----------------------

Either user can use the ``xo delete`` command to delete their local XO data.
This includes all games, the saved URL, and the username.

.. code-block:: console

   $ xo delete


Using Authentication with the xo Client
=======================================

The XO client supports optional authentication. If the REST API is connected
to an authentication proxy, you can point the XO client at it with the ``--url``
argument. You  must also specify your authentication information using the
``--auth-user [user]`` and ``--auth-password [password]`` options for each
``xo`` command.

Note that the value of the ``--auth-user`` argument is **not** the
same username that is entered with the ``--username`` argument.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

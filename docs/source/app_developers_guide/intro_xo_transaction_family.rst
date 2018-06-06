**************************************
Playing with the XO Transaction Family
**************************************

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
   `JavaScript <https://github.com/hyperledger/sawtooth-sdk-javascript/blob/master/examples/xo/>`__,
   and Python (``xo-tp-python``). These transaction
   processors implement the business logic of XO game play.

 * An ``xo`` client: A set of commands that provide a command-line interface
   for playing XO. The ``xo`` client handles the construction and submission
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
with the ``xo`` client. Each ``xo`` command is a transaction that the client
submits to the validator via the REST API.


Prerequisites
-------------

* A working Sawtooth development environment, as described in
  :doc:`/app_developers_guide/installing_sawtooth`. This environment must be
  running a validator, a REST API, and the Settings transaction processor.
  (The IntegerKey transaction processor is not used in this procedure.)

* This procedure also requires the XO transaction processor. The Docker and AWS
  procedures start it automatically. For Ubuntu, this procedure shows how to
  start the XO transaction processor if necessary.


Step 1: Confirm Connectivity to the REST API
--------------------------------------------

#. Connect to your development environment, as described in the procedure for
   your platform in :doc:`installing_sawtooth`.

#. Verify that you can connect to the REST API.

   * Docker: See :ref:`confirming-connectivity-docker-label`

   * Ubuntu: See :doc:`/app_developers_guide/installing_sawtooth`

   * AWS: See :ref:`confirming-connectivity-aws-label`

   .. Important::

      The ``xo`` client sends requests to update and query the blockchain to the
      URL of the REST API (by default, ``http://127.0.0.1:8008``).

      If the REST API's URL is not ``http://127.0.0.1:8008``, you must add the
      ``--url`` argument to each ``xo`` command in this procedure.

      For example, the following command specifies the URL for the Docker demo
      application environment when creating a new game:

      .. code-block:: console

         $ xo create my-game --username jack --url http://rest-api:8008


Step 2. Ubuntu only: Start the XO Transaction Processor
-------------------------------------------------------

If you did not start the XO transaction processor on your Ubuntu application
development environment, start it now.

#. Open a new terminal window (the xo window).

#. Check whether the XO transaction processor is running.

   .. code-block:: console

      user@xo$ ps aux | grep [x]o-tp
      root      1546  0.0  0.1  52700  3776 pts/2    S+   19:15   0:00 sudo -u sawtooth xo-tp-python -v
      sawtooth  1547  0.0  1.5 277784 31192 pts/2    Sl+  19:15   0:00 /usr/bin/python3 /usr/bin/xo-tp-python -v

#. If the output does not show that ``/usr/bin/xo-tp-python`` is running, start
   the XO transaction processor with the following command:

   .. code-block:: console

      user@xo$ sudo -u sawtooth xo-tp-python -v

For more information, see Step 5.3 in :doc:`ubuntu`.


Step 3. Create Players
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


Step 4. Create a Game
---------------------

Create a game named ``my-game`` with the following command:

.. code-block:: console

    $ xo create my-game --username jack

.. note::

   The ``--username`` argument is required for ``xo create`` and ``xo take``
   so that a single player (you) can play as two players. By default,
   ``<username>`` is the Linux user name of the person playing the game.

Verify that the ``create`` transaction was committed by displaying the list of
existing games:

.. code-block:: console

    $ xo list
    GAME            PLAYER 1        PLAYER 2        BOARD     STATE
    my-game                                         --------- P1-NEXT

.. note::

   The ``xo list`` command is a wrapper that provides a quick way to show game
   state rather than using ``curl`` with the REST API's URL to request state.


Step 5. Take a Space as Player 1
--------------------------------

.. note::

   The first player to issue an ``xo take`` command to a newly created game is
   recorded as ``PLAYER 1`` . The second player to issue a ``take`` command is
   recorded by username as ``PLAYER 2``.

   The ``--username`` argument determines where the ``xo`` client should look
   for the player's key to sign the transaction. By default, if you're logged in
   as ``root``, ``xo`` would look for the key file named
   ``~/.sawtooth/keys/root.priv``. Instead, the following command specifies
   that ``xo`` should use the key file ``~/.sawtooth/keys/jack.priv``.

Start playing tic-tac-toe by taking a space as the first player, Jack. In this
example, Jack takes space 5:

.. code-block:: console

    $ xo take my-game 5 --username jack


This diagram shows the number of each space.

 .. code-block:: none

     1 | 2 | 3
    ---|---|---
     4 | 5 | 6
    ---|---|---
     7 | 8 | 9

**What Happens During a Game Move?**

Each ``xo`` command is a transaction. A successful transaction updates global
state with the game name, board state, game state, and player keys, using
this format:

.. code-block:: none

      <game-name>,<board-state>,<game-state>,<player1-key>,<player2-key>

Each time a player attempts to take a space, the transaction processor will
verify that their username matches the name of the player whose turn it is.
This ensures that no player is able to mark a space out of turn.

After each turn, the XO transaction processor scans the board state for a
win or tie. If either condition occurs, no more ``take`` actions are allowed
on the finished game.


Step 6. Take a Space as Player 2
--------------------------------

Next, take a space on the board as player 2, Jill.  In this example,
Jill takes space 1:

.. code-block:: console

    $ xo take my-game 1 --username jill


Step 7. Show the Current Game Board
-----------------------------------

Whenever you want to see the current state of the game board, enter the
following command:

.. code-block:: console

    $ xo show my-game

The output includes the game name, the first six characters of each player's
public key, the game state, and the current board state. This example shows the
game state ``P1-NEXT`` (player 1 has the next turn) and a board with Jack's X in
space 5 and Jill's O in space 1.

.. code-block:: console

    GAME:     : my-game
    PLAYER 1  : 02403a
    PLAYER 2  : 03729b
    STATE     : P1-NEXT

      O |   |
     ---|---|---
        | X |
     ---|---|---
        |   |

This ``xo`` client formats the global state data so that it's easier to read
than the state returned to the transaction processor:

.. code-block:: none

   my-game,O---X----,P1-NEXT,02403a...,03729b...


Step 8. Continue the Game
-------------------------

Players take turns using ``xo take my-game <space>`` to mark spaces on the grid.

You can continue the game until one of the players wins or the game ends in a
tie, as in this example:

.. code-block:: console

    $ xo show my-game
    GAME:     : my-game
    PLAYER 1  : 02403a
    PLAYER 2  : 03729b
    STATE     : TIE

      O | X | O
     ---|---|---
      X | X | O
     ---|---|---
      X | O | X


Step 9. Delete the Game
-----------------------

Either player can use the ``xo delete`` command to remove the game data from
global state.

.. code-block:: console

   $ xo delete my-game


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

*********************
XO Transaction Family
*********************

Overview
========

The XO transaction family allows users to play the simple board game
`tic-tac-toe <https://en.wikipedia.org/wiki/Tic-tac-toe>`_ (also known as
*Noughts and Crosses* or *X’s and O’s*). For more information, see
:doc:`../app_developers_guide/intro_xo_transaction_family`.

State
=====

An XO state entry consists of the UTF-8 encoding of a string with
exactly four commas, which is formatted as follows:

``<name>,<board>,<game-state>,<player-key-1>,<player-key-2>``

* ``<name>`` is the game name as a non-empty string not containing the
  character ``|``
* ``<board>`` represents the game board as a string of length 9 containing only
  `O`, `X`, or `-`
* ``<game-state>`` is one of the following: `P1-NEXT`, `P2-NEXT`, `P1-WIN`,
  `P2-WIN`, or `TIE`
* ``<player-key-1>`` and ``<player-key-2>`` are the (possibly empty) public keys
  associated with the game's players

In the event of a hash collision (two or more state entries
sharing the same address), the colliding state entries will stored as
the UTF-8 encoding of the string ``<a-entry>|<b-entry>|...``, where
the entries are sorted alphabetically.


Addressing
----------

XO data is stored in state using addresses generated from the XO
family name and the name of the game being stored. In particular, an
XO address consists of the first 6 characters of the SHA-512 hash of
the UTF-8 encoding of the string "xo" (which is "5b7349") plus the
first 64 characters of the SHA-512 hash of the UTF-8 encoding of the
game name.

For example, the XO address for a game called "mygame" could be
generated as follows:

.. code-block:: pycon

    >>> hashlib.sha512('xo'.encode('utf-8')).hexdigest()[:6] + hashlib.sha512('mygame'.encode('utf-8')).hexdigest()[:64]
    '5b7349700e158b598043efd6d7610345a75a00b22ac14c9278db53f586179a92b72fbd'


Transaction Payload
===================

An XO transaction request payload consists of the UTF-8 encoding of a
string with exactly two commas, which is formatted as follows:

``<name>,<action>,<space>``

* ``<name>`` is the game name as a non-empty string not containing the character
  ``|``. If ``<action>`` is `create`, the new name must be unique.
* ``<action>`` is the game action: `create`, `take`, or `delete`
* ``<space>`` is the location on the board, as an integer between 1-9
  (inclusive), if ``<action>`` is `take`


Transaction Header
==================

Inputs and Outputs
------------------

The inputs and outputs for an XO transaction are just the state
address generated from the transaction game name.


Dependencies
------------

XO transactions have no explicit dependencies.


Family
------

* family_name: "xo"
* family_version: "1.0"


.. _xo-execution-label:

Execution
=========

The XO transaction processor receives a transaction request and a
state dictionary. If it is valid, the transaction request payload will
have a game name, an action, and, if the action is `take`, a space.

1. If the action is `create`, the transaction is invalid if the
   game name is already in state dictionary. Otherwise, the transaction
   processor will store a new state entry with board `---------` (i.e. a blank
   board), game state `P1-NEXT`, and empty strings for both player
   keys.

#. If the action is `take`, the transaction is invalid if the
   game name is not in the state dictionary. Otherwise, there is a
   state entry under the game name with a board, game state, player-1
   key, and player-2 key. The transaction is invalid if:

   * the game state is `P1-WIN`, `P2-WIN`, or `TIE`, or
   * the game state is `P1-NEXT` and the player-1 key is not null and different
     from the transaction signing key, or
   * the game state is `P2-NEXT` and the player-2 key is nonnull and different
     from the transaction signing key, or
   * the space-th character in the board-string is not `-`.

   Otherwise, the transaction processor will update the state entry
   according to the following rules:

   a. Player keys - If the player-1 key is null (the empty string), it
      will be updated to key with which the transaction was signed. If
      the player-1 key is nonnull and the player-2 key is null, the
      player-2 will be updated to the signing key. Otherwise, the
      player keys will not be changed.

   b. Board - If the game state is `P1-NEXT`, the updated board will
      be the same as the initial board except with the space-th
      character replaced by the character `X`, and the same for the
      state `P2-NEXT` and the character `O`.

   c. Game state - Call the first three characters of the board string
      its first row, the next three characters its second row, and the
      last three characters its third row.If any of the rows consist
      of the same character, say that character has a *win* on the
      board. If all the rows have the same first character or the same
      second character or the same third character (the board's
      columns), that character has a win on the board. If the first
      character of the first row and the second character of the
      second row and the third character of the third row are the
      same, or if the third character of the first row and the second
      character of the second row and the first character of the third
      row are the same, that character has a win on the board.

      - If `X` has a win on the board and `O` doesn't, the updated state will be
        `P1-WINS`.
      - If `O` has a win on the board and `X` doesn't, the updated state will be
        `P2-WINS`.
      - Otherwise, if the updated board doesn't contain `-` (if the board has no
        empty spaces), the updated state will be `TIE`.
      - Otherwise, the updated state will be `P2-NEXT` if the initial state is
        `P1-NEXT` and `P1-NEXT` and if the initial state is `P2-NEXT`.

#. If the action is `delete`, the transaction is invalid if the game name is not
   in the state dictionary. Otherwise, the transaction processor will delete the
   state entry for the game.


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

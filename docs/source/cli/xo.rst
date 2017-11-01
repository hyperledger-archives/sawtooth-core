..
   Copyright 2017 Intel Corporation

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.

.. _xo-cli-reference-label:

******
XO CLI
******

xo
==

The ``xo`` command allows users to play a simple board game known
variously as tic-tac-toe, noughts and crosses, and XO.

.. literalinclude:: output/xo_usage.out
   :language: console
   :linenos:

xo create
=========

Sends a transaction to start an xo game with the identifier
``<name>``. This transaction will fail if a game already exists with
the name ``<name>``.

.. literalinclude:: output/xo_create_usage.out
   :language: console
   :linenos:

xo list
=======

Displays information for all xo games in state, showing the players,
the game state, and the board for each game.

.. literalinclude:: output/xo_list_usage.out
   :language: console
   :linenos:

xo show
=======

Displays the xo game ``<name>``, showing the players, the game state,
and the board.

.. literalinclude:: output/xo_show_usage.out
   :language: console
   :linenos:

xo take
=======

Sends a transaction to make a move in the xo game ``<name>``, taking
``<space>``. This transaction will fail if the game ``<name>`` does
not exist, if it is not the sender’s turn, or if ``<space>`` is
already taken.

.. literalinclude:: output/xo_take_usage.out
   :language: console
   :linenos:

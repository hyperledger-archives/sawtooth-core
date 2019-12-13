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

**
xo
**

The ``xo`` command starts the XO transaction processor.

This command demonstrates an example client that uses the XO transaction
family to play a simple game of Tic-tac-toe (also known as Noughts and Crosses,
or X's and O's). This command handles the construction and submission of
transactions to a running validator via the URL of the validator's REST API.

Before playing a game, you must start a validator, the XO transaction processor,and the REST API. The XO client sends requests to update and query the
blockchain to the URL of the REST API (by default, ``http://127.0.0.1:8008``).

For more information on requirements and game rules, see
:doc:`../app_developers_guide/intro_xo_transaction_family`.

The ``xo`` command provides subcommands for playing XO on the command line.

.. literalinclude:: output/xo_usage.out
   :language: console

xo create
=========

The ``xo create`` subcommand starts an XO game with the specified name.

.. literalinclude:: output/xo_create_usage.out
   :language: console

xo list
=======

The ``xo list`` subcommand displays information for all XO games in state.

.. literalinclude:: output/xo_list_usage.out
   :language: console

xo show
=======

The ``xo show`` subcommand displays information about the specified XO game.

.. literalinclude:: output/xo_show_usage.out
   :language: console

xo take
=======

The ``xo take`` subcommand makes a move in an XO game by sending a transaction
to take the identified space.  This transaction will fail if the game `name` does not exist, if it is not the sender’s turn, or if `space` is
already taken.

.. literalinclude:: output/xo_take_usage.out
   :language: console

xo delete
=========

The ``xo delete`` subcommand deletes an existing xo game.

.. literalinclude:: output/xo_delete_usage.out
   :language: console

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

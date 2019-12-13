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

.. _intkey-cli-reference-label:

******
intkey
******

The ``intkey`` command starts the IntegerKey transaction processor,
which provides functions that can be used to test deployed ledgers.

The ``intkey`` command provides subcommands to set, increment, and
decrement the value of entries stored in a state dictionary.

.. literalinclude:: output/intkey_usage.out
   :language: console

intkey set
==========

The ``intkey set`` subcommand sets a key (`name`) to the specified value.
This transaction will fail if the value is less than 0 or greater than
2\ :sup:`32` - 1.

.. literalinclude:: output/intkey_set_usage.out
   :language: console

intkey inc
==========

The ``intkey inc`` subcommand increments a key (`name`) by the specified value.
This transaction will fail if the key is not set or if the resulting value
would exceed 2\ :sup:`32` - 1.

.. literalinclude:: output/intkey_inc_usage.out
   :language: console

intkey dec
==========

The ``intkey dec`` subcommand decrements a key (`name`) by the specified value.
This transaction will fail if the key is not set or if the resulting value
would be less than 0.

.. literalinclude:: output/intkey_dec_usage.out
   :language: console

intkey show
===========

The ``intkey show`` subcommand displays the value of the specified key (`name`).

.. literalinclude:: output/intkey_show_usage.out
   :language: console

intkey list
===========

The ``intkey list`` subcommand displays the value of all keys.

.. literalinclude:: output/intkey_list_usage.out
   :language: console

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

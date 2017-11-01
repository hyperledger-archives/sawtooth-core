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

**************
IntegerKey CLI
**************

intkey
======

The IntegerKey transaction family allows users to set, increment, and
decrement the value of entries stored in a state dictionary.

.. literalinclude:: output/intkey_usage.out
   :language: console
   :linenos:

intkey set
==========

Sends a transaction to set ``<name>`` to ``<value>``. This transaction
will fail if ``<value>`` is less than 0 or greater than 2\
:sup:`32` - 1.

.. literalinclude:: output/intkey_set_usage.out
   :language: console
   :linenos:

intkey inc
==========

Sends a transaction to increment ``<name>`` by ``<value>``. This
transaction will fail if ``<name>`` is not set or if the resulting
value would exceed 2\ :sup:`32` - 1.

.. literalinclude:: output/intkey_inc_usage.out
   :language: console
   :linenos:

intkey dec
==========

Sends a transaction to increment ``<name>`` by ``<value>``. This
transaction will fail if ``<name>`` is not set or if the resulting
value would be less than 0.

.. literalinclude:: output/intkey_dec_usage.out
   :language: console
   :linenos:

intkey show
===========

Displays the value of the intkey entry ``<name>``.

.. literalinclude:: output/intkey_show_usage.out
   :language: console
   :linenos:

intkey list
===========

Displays the value of all intkey entries in state.

.. literalinclude:: output/intkey_list_usage.out
   :language: console
   :linenos:

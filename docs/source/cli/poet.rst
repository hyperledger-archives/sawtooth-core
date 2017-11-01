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

.. _poet-cli-reference-label:

********
PoET CLI
********

The PoET CLI initializes the proof-of-elapsed-time consensus mechanism
for Sawtooth by generating enclave setup information and creating a
Batch for the genesis block. For more information, see
:doc:`/architecture/poet`.

poet
====

The poet command generates information for configuring a node to use
Sawtooth with the PoET consensus method. The genesis subcommand
creates a Batch for the genesis block. The enclave subcommand
generates enclave setup information.

.. literalinclude:: output/poet_usage.out
   :language: console
   :linenos:

poet genesis
============

The ``poet genesis`` subcommand creates a Batch for the genesis Block.

.. literalinclude:: output/poet_genesis_usage.out
   :language: console
   :linenos:

poet enclave
============

The ``poet enclave`` subcommand generates enclave setup information.

.. literalinclude:: output/poet_enclave_usage.out
   :language: console
   :linenos:

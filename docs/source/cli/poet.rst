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

****
poet
****

The ``poet`` command initializes the Proof of Elapsed Time (PoET) consensus
mechanism for Sawtooth by generating enclave setup information and creating a
Batch for the genesis block. For more information, see
:doc:`/architecture/poet`.

The ``poet`` command provides subcommands for configuring a node to use
Sawtooth with the PoET consensus method.

.. literalinclude:: output/poet_usage.out
   :language: console
   :linenos:

poet registration
=================

The ``poet registration`` subcommand provides a command to work with
the PoET validator registry.

.. literalinclude:: output/poet_registration_usage.out
   :language: console
   :linenos:

poet registration create
========================

The ``poet registration create`` subcommand creates a batch to enroll
a validator in the network's validator registry. It must be run from
the validator host wishing to enroll.

.. literalinclude:: output/poet_registration_create_usage.out
   :language: console
   :linenos:

poet enclave
============

The ``poet enclave`` subcommand generates enclave setup information.

.. literalinclude:: output/poet_enclave_usage.out
   :language: console
   :linenos:

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

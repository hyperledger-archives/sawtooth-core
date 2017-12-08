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

************************************************
Identity Transaction Processor CLI (identity-tp)
************************************************

The Identity transaction processor CLI, ``sawtooth-identity``, handles
on-chain permissioning for transactor and validator keys to streamline
managing identities for lists of public keys.

The Settings transaction processor is required when using the Identity
transaction processor.

identity-tp
===========

The ``identity-tp`` command starts an Identity transition processor, which
is responsible for applying the changes to on-chain permissions that are used
by the Sawtooth platform.

In order to send identity transactions, your public key
must be stored in ``sawtooth.identity.allowed_keys``.

.. literalinclude:: output/identity-tp_usage.out
   :language: console
   :linenos:

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

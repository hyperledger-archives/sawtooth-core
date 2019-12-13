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

.. _sawset-reference-label:

******
sawset
******

The ``sawset`` command is used to work with settings proposals.

Sawtooth supports storing settings on-chain. The ``sawset``
subcommands can be used to view the current proposals, create
proposals, vote on existing proposals, and produce setting values
that will be set in the genesis block.

.. literalinclude:: output/sawset_usage.out
   :language: console

sawset genesis
==============

The ``sawset genesis`` subcommand creates a Batch of settings
proposals that can be consumed by ``sawadm genesis`` and used
during genesis block construction.

.. literalinclude:: output/sawset_genesis_usage.out
   :language: console

sawset proposal
===============

The Settings transaction family supports a
simple voting mechanism for applying changes to on-chain settings.
The ``sawset proposal`` subcommands provide tools to view,
create and vote on proposed settings.

.. literalinclude:: output/sawset_proposal_usage.out
   :language: console

sawset proposal create
======================

The ``sawset proposal create`` subcommand creates proposals
for settings changes. The change may be applied immediately or after a
series of votes, depending on the vote threshold setting.

.. literalinclude:: output/sawset_proposal_create_usage.out
   :language: console

sawset proposal list
====================

The ``sawset proposal list`` subcommand displays the
currently proposed settings that are not yet active. This list of
proposals can be used to find proposals to vote on.

.. literalinclude:: output/sawset_proposal_list_usage.out
   :language: console

sawset proposal vote
====================

The ``sawset proposal vote`` subcommand votes for a specific
settings-change proposal. Use ``sawset proposal list`` to
find the proposal id.

.. literalinclude:: output/sawset_proposal_vote_usage.out
   :language: console

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

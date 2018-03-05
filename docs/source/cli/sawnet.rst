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

.. _sawnet-reference-label:

******
sawnet
******

The ``sawnet`` command is used to interact with an entire
network of Sawtooth nodes.

.. literalinclude:: output/sawnet_usage.out
   :language: console


sawnet compare-chains
=====================

The ``sawnet compare-chains`` subcommand compares chains across the specified
nodes.

.. literalinclude:: output/sawnet_compare-chains_usage.out
   :language: console

sawnet peers
============

.. literalinclude:: output/sawnet_peers_usage.out
   :language: console

sawnet peers list
=================

The ``sawnet peers list`` subcommand displays the peers of the specified nodes.

.. literalinclude:: output/sawnet_peers_list_usage.out
   :language: console

sawnet peers graph
==================

The ``sawnet peers graph`` subcommand displays a file called ``peers.dot``
that describes the peering arrangement of the specified nodes.

.. literalinclude:: output/sawnet_peers_graph_usage.out
   :language: console

.. _about-dynamic-consensus-label:

***********************
About Dynamic Consensus
***********************

Sawtooth :term:`dynamic consensus` lets you choose from a variety of consensus
algorithms for the network.

* Each consensus type has a :term:`consensus engine` that communicates with the
  validator through the :term:`consensus API`. Each node in the network must run
  the same consensus engine.

* The validator listens for the consensus engine on the `consensus endpoint`
  (by default, ``tcp://127.0.0.1:5050``). For more information, see
  :doc:`/sysadmin_guide/off_chain_settings`.

* The consensus type is controlled by the on-chain settings
  ``sawtooth.consensus.algorithm.name`` and
  ``sawtooth.consensus.algorithm.version``. These settings are required.

The rest of this topic summarizes how to configure consensus and lists the
settings and requirements for each supported consensus type:
:ref:`PBFT <pbft-consensus-label>`,
:ref:`PoET <poet-consensus-label>`,
:ref:`Raft <raft-consensus-label>`, and
:ref:`Devmode <devmode-consensus-label>`.

.. note::

   **Compatibility with Sawtooth 1.0**:
   Sawtooth provides defaults for backward compatibility with Sawtooth 1.0
   (and earlier versions), when Devmode and PoET were the only supported
   consensus algorithms.

   The following defaults apply to a network that was created with Sawtooth
   release 1.1 or earlier:

   * If ``sawtooth.consensus.algorithm.version`` is not set, the default version
     is ``0.1``.

   * If ``sawtooth.consensus.algorithm.name`` is not set, Sawtooth checks for
     the deprecated setting ``sawtooth.consensus.algorithm``. If this setting
     exists, Sawtooth uses the specified consensus.

   * Otherwise, Sawtooth uses Devmode consensus.

   A new network **must** specify the ``sawtooth.consensus.algorithm.version``
   and ``sawtooth.consensus.algorithm.name`` settings.

   **Important:** In release 1.1 and later, a consensus engine is always
   required. The same consensus engine must be running on all nodes in the
   network.


Configuring Consensus for a New Network
=======================================

To configure the initial consensus, create a consensus proposal for the
:term:`genesis block`, then start the consensus engine and any transaction
processors that are required by that consensus type.

1. The administrator of the first node uses the command ``sawset proposal
   create`` to specify the consensus settings in the genesis block.
   See :doc:`/sysadmin_guide/setting_up_sawtooth_network` for this procedure.

#. On each node, the administrator installs and starts the consensus engine and
   any transaction processors required for consensus (such as PoET Validator
   Registry). See :doc:`/sysadmin_guide/systemd` for this procedure.

When each node joins the network, it reads the on-chain consensus settings, then
starts using the consensus engine to process blocks.


Changing Consensus on a Running Network
=======================================

To change to a different consensus, start the new consensus engine on all nodes,
plus any transaction processors that are required by that consensus type. Then
submit a consensus change proposal.

.. note::

   Administrators should coordinate the change to a new consensus. For some
   consensus types, the network could slow or become stalled if some nodes have
   not started the new consensus engine.

1. If the network has forked, stop all nodes except the one with the preferred
   blocks.

#. Each administrator installs and starts the new consensus engine and any
   related transaction processors. See :doc:`/sysadmin_guide/installation` and
   :doc:`/sysadmin_guide/systemd` for these procedures.

#. One administrator uses the command ``sawset proposal create`` to submit a
   transaction with the new on-chain consensus settings. For an example, see
   :doc:`creating_genesis_block` or :ref:`config-validator-for-PoET-SGX-label`.

   .. important::

      This node or user must have permission to change on-chain settings.
      Usually, the node that created the genesis block has the appropriate
      permissions.  For more information, see
      :ref:`config-onchain-txn-perm-label`.

   When the block containing this transaction is committed, the network changes
   to the new consensus.

#. For each node, do not stop the previous consensus engine (and any related
   transaction processors) until the node has processed all the blocks that
   were submitted using the previous consensus.

#. If a new node joins the network, it must run both consensus engines and all
   related transaction processors. The original consensus is required to process
   the first set of blocks.


.. _pbft-consensus-label:

PBFT Consensus
==============

:term:`Sawtooth PBFT <PBFT consensus>` is a voting-based, non-forking
consensus algorithm with finality that provides Byzantine Fault Tolerance
(BFT). PBFT is best for small, consortium-style networks that do not require
open membership. For more information, see the
`PBFT documentation <https://sawtooth.hyperledger.org/docs/pbft/nightly/master/>`__.

Requirements:

* A PBFT network must have at least four nodes.

* The genesis block must include the validator public keys of all nodes in the
  initial network.

* Each node must install the PBFT consensus engine package,
  ``sawtooth-pbft-engine``.

* Each node must run the PBFT consensus engine:

  * Service: ``sawtooth-pbft-engine.service``
  * Executable: ``pbft-engine``

  For more information, see :doc:`/sysadmin_guide/systemd`. (To start the
  consensus engine on the command line, see
  :ref:`start-sawtooth-first-node-label`).

* Specify static peering when starting each validator. Use the ``--peering``
  option when starting the validator (see :doc:`/cli/sawtooth-validator`) or
  set the off-chain ``peers`` setting in the ``validator.toml`` configuration
  file (see :doc:`configuring_sawtooth`).

* Use these on-chain settings to configure PBFT consensus:

  .. code-block:: none

     sawtooth.consensus.algorithm.name=pbft
     sawtooth.consensus.algorithm.version=1.0
     sawtooth.consensus.pbft.members=["VAL1KEY","VAL2KEY",...,"VALnKEY"]

  .. note::

     Use double quotes around each member key in a comma-separated list
     with no spaces. If using the ``sawset proposal create`` command, you must
     also surround the entire members string with single quotes (to protect the
     double quotes).

  See :doc:`/sysadmin_guide/creating_genesis_block` for more information on the
  version and validator public keys for the PBFT member list .

* For optional PBFT consensus settings, see
  `Configuring PBFT <https://sawtooth.hyperledger.org/docs/pbft/nightly/master/configuring-pbft.html>`__
  in the PBFT documentation.


.. _poet-consensus-label:

PoET Consensus
==============

:term:`PoET <PoET consensus>` is a Nakamoto-style (lottery) consensus algorithm
that is designed to support large production networks with open or
consortium-style membership. For more information, see
:doc:`/architecture/poet`.

Sawtooth provides two versions of PoET consensus: *PoET SGX* (also called
PoET BFT) and *PoET simulator* (also called PoET CFT). For more information,
see :ref:`dynamic-consensus-label`.

  .. important::

     To learn which versions of Sawtooth support PoET SGX consensus, see
     :doc:`/sysadmin_guide/configure_sgx` in the System Administrator's Guide.

Requirements:

* A PoET network must have at least three nodes, but is designed for larger
  networks.

* Each node must install the PoET consensus engine package,
  ``python3-sawtooth-poet-engine``.

* Each node must run the PoET consensus engine:

  * Service: ``sawtooth-poet-engine.service``
  * Executable: ``poet-engine``

* Each node in the network must also run the PoET Validator Registry transaction
  processor (included in the ``sawtooth`` package):

  * Service: ``sawtooth-poet-validator-registry-tp.service``
  * Executable: ``poet-validator-registry-tp``

* Use these on-chain settings for the PoET consensus engine:

  .. code-block:: none

     sawtooth.consensus.algorithm.name=PoET
     sawtooth.consensus.algorithm.version=0.1
     sawtooth.poet.report_public_key_pem="$(cat * /etc/sawtooth/simulator_rk_pub.pem)"
     sawtooth.poet.valid_enclave_measurements=$(poet enclave measurement)
     sawtooth.poet.valid_enclave_basenames=$(poet enclave basename)

* For a PoET test network with less than 10 or 12 nodes, disable the
  defense-in-depth tests with these settings:

  .. code-block:: none

     sawtooth.poet.block_claim_delay=1
     sawtooth.poet.key_block_claim_limit= 100000
     sawtooth.poet.ztest_minimum_win_count=999999999


.. _raft-consensus-label:

Raft Consensus
==============

:term:`Sawtooth Raft <Raft consensus>` provides a simple consensus algorithm
that is easy to understand.  It is leader-based, crash fault tolerant, and
does not fork. For more information, see the
`Raft documentation <https://sawtooth.hyperledger.org/docs/raft/nightly/master/>`__.

.. note::

   Sawtooth Raft is currently a prototype (not yet released). For more
   information, see the
   `sawtooth-raft <https://github.com/hyperledger/sawtooth-raft>`__ repository.

Requirements:

* Each node must install the Raft consensus engine package,
  ``sawtooth-raft-engine``.

* Each node must run the Raft consensus engine:

  * Service: ``sawtooth-raft-engine.service``
  * Executable: ``raft-engine``

  For more information, see :doc:`/sysadmin_guide/systemd`. (To start the
  consensus engine on the command line, see
  :ref:`start-sawtooth-first-node-label`).

* Specify static peering when starting each validator. Use the ``--peering``
  option when starting the validator (see :doc:`/cli/sawtooth-validator`) or
  set the off-chain ``peers`` setting in the ``validator.toml`` configuration
  file (see :doc:`configuring_sawtooth`).

* Use these on-chain settings for Raft consensus:

  .. code-block:: none

     sawtooth.consensus.algorithm.name=raft
     sawtooth.consensus.algorithm.version=[VERSION]
     sawtooth.consensus.raft.peers=[VAL1KEY,VAL2KEY,...,VALnKEY]

  For the version number, see the ``Cargo.toml`` file. Use only the first two
  digits (for example, `0.1`).

  For ``VALxKEY``, specify the validator public key of each node in the network.

* For other on-chain settings for Raft, see
  `Optional Settings <https://sawtooth.hyperledger.org/docs/raft/nightly/master/configuring_deploying.html#on-chain-settings>`__
  in the Raft documentation.


.. _devmode-consensus-label:

Devmode Consensus
=================

Devmode uses a simplified random-leader algorithm. It is intended for testing
a transaction processor with a single Sawtooth node. Do not use Devmode for a
production network.

Requirements:

* The node must install the Devmode consensus engine package,
  ``sawtooth-devmode-engine-rust``.

* The node must run the Devmode consensus engine ``devmode-engine-rust``.
  For example:

  .. code-block:: console

     $ sudo -u sawtooth devmode-engine-rust -vv --connect tcp://localhost:5050

  For more information, see :doc:`/app_developers_guide/installing_sawtooth`.

* Use these on-chain settings for the Devmode consensus engine:

  .. code-block:: none

     sawtooth.consensus.algorithm.name=Devmode
     sawtooth.consensus.algorithm.version=0.1

  Optional settings control how long a validator should wait before attempting
  to publish a block. If one (or both) of these options is a nonzero value,
  the Devmode algorithm picks a random value between the maximum and minimum.

  * ``sawtooth.consensus.max_wait_time``: Maximum wait time, in seconds.
    The default is 0 (no wait).
  * ``sawtooth.consensus.min_wait_time``: Minimum wait time, in seconds.
    The default is 0 (no wait).


.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

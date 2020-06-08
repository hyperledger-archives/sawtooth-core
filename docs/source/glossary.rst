Glossary
========

This glossary defines Hyperledger Sawtooth terms and concepts.

.. glossary::

  batch
    Group of related transactions.
    In Sawtooth, a batch is the atomic unit of state change for the blockchain.
    A batch can contain one or more transactions. For a batch with multiple
    transactions, if one transaction fails, all transactions in that batch fail.
    (The client application is responsible for handling failure appropriately.)
    For more information, see :doc:`architecture/transactions_and_batches`.

  blockchain
    Distributed ledger that records transactions, in chronological order,
    shared by all participants in a Sawtooth network. Each block on the
    blockchain is linked by a cryptographic hash to the previous block.

  consensus
    Process of reaching agreement among a group of participants (nodes on a
    Sawtooth network), some of which could be faulty or malicious. Sawtooth
    supports many types of consensus algorithms with the :term:`dynamic
    consensus` feature.

  consensus API
    Interface that allows a `consensus engine` to interact with the validator
    in order to handle consensus functionality in a separate process.

  consensus engine
    Sawtooth component that provides consensus-specific functionality for a
    Sawtooth node. The consensus engine runs as a separate process on the node
    and communicates with the validator through the *consensus API*.

  core
    See :term:`Sawtooth core`.

  Devmode consensus
    (Formerly "dev mode consensus".)
    Simple random-leader consensus algorithm that can be used to test a
    transaction processor on a single Sawtooth node. (Devmode is short for
    "developer mode".) Devmode consensus is not recommended for a multiple-node
    network; it should not be used for production.

  distributed ledger
    See :term:`blockchain`.

  dynamic consensus
    Sawtooth feature that allows a variety of consensus algorithms (formerly
    called "pluggable consensus"). Dynamic consensus allows each Sawtooth
    network to choose the best consensus for its purposes, as specified by
    on-chain settings in the genesis block. Sawtooth supports the ability to
    change the consensus algorithm on a running network by submitting a
    transaction. For more information, see
    :ref:`dynamic-consensus-label`.

  genesis block
    First block on the blockchain. The genesis block initializes the
    Sawtooth network.

  global state
    Database that stores a local (validator-specific) record of transactions for
    the blockchain. Sawtooth represents state in a single instance of a
    Merkle-Radix tree on each Sawtooth node.  For more information, see
    :doc:`architecture/global_state`.

  identity
    Sample transaction family that handles on-chain permissions (settings
    stored on the blockchain) for transactor and validator keys. This
    transaction family demonstrates how to streamline managing identities
    for lists of public keys. For more information, see
    :doc:`transaction_family_specifications/identity_transaction_family`.

  IntegerKey
    Sample transaction family with only three operations (set, increment, and
    decrement) that can be used to test deployed ledgers. IntegerKey is called
    *intkey*. For more information, see
    :doc:`transaction_family_specifications/integerkey_transaction_family`.

  journal
    Group of Sawtooth core processes that are responsible for maintaining and
    extending the blockchain for the validator. For more information, see
    :doc:`architecture/journal`.

  Merkle-Radix tree
    Addressable data structure that stores state data. A Merkle-Radix tree
    combines the benefits of a Merkle tree (also called a "hash tree"), which
    stores successive node hashes from leaf-to-root upon any changes to the
    tree, and a Radix tree, which has addresses that uniquely identify the
    paths to leaf nodes where information is stored.  For more information, see
    :ref:`merkle-radix-overview-label`.

  node
    Participant in Sawtooth network. Each node runs a single validator, a
    REST API, a consensus engine, and one or more transaction processors.

  off-chain setting
    Setting or value that is stored locally, rather than on the blockchain.

  on-chain setting
    Setting or value that is stored on the blockchain (also referred to as
    "in state") so that all participants on the network can access that
    information.

  PBFT consensus
    Practical Byzantine Fault Tolerance, a voting-based consensus algorithm with
    `Byzantine fault tolerance (BFT) <https://en.wikipedia.org/wiki/Byzantine_fault_tolerance>`__
    that has finality (does not fork). Sawtooth PBFT extends the
    `original PBFT algorithm
    <https://www.usenix.org/legacy/events/osdi99/full_papers/castro/castro_html/castro.html>`__
    with features such as dynamic network membership, regular view changes,
    and a block catch-up procedure.

  permissioned network
    Restricted network of Sawtooth nodes. A permissioned network
    typically includes multiple parties with a mutual interest but without
    the mutual trust found in a network controlled by a single company or
    entity.

    The blockchain stores the settings that specify permissions, such as roles
    and identities, so that all participants in the network can access this
    information.

  PoET consensus
    Proof of Elapsed Time, a Nakamoto-style consensus algorithm that is designed
    to support large networks. PoET does not have finality (can fork).

    Sawtooth offers two version of PoET consensus:

    * *PoET-SGX* relies on a Trusted Execution Environment (TEE), such as
      |Intel (R)| Software Guard Extensions (SGX), to implement a
      leader-election lottery system. PoET-SGX is sometimes called *PoET/BFT*
      because it is
      `Byzantine fault tolerant <https://en.wikipedia.org/wiki/Byzantine_fault_tolerance>`__.

    * *PoET simulator* provides the same consensus algorithm on a system without
      a Trusted Execution Environment. PoET simulator is also called *PoET/CFT*
      because it is crash fault tolerant, not Byzantine fault tolerant.

  Raft consensus
    Leader-based consensus algorithm that is designed for small networks with
    a restricted membership. Raft is crash fault tolerant, not Byzantine fault
    tolerant, and has finality (does not fork). For more information, see
    `Raft (computer science) on Wikipedia <https://en.wikipedia.org/wiki/Raft_(computer_science)>`__
    and the `Sawtooth Raft documentation
    <https://sawtooth.hyperledger.org/docs/raft/nightly/master/introduction.html>`__.

  REST API
    In Sawtooth, a core component that adapts communication with a validator to
    HTTP/JSON standards. Sawtooth includes a REST API that is used by clients
    such as the Sawtooth CLI commands. Developers can use this REST API or
    develop custom APIs for client-validator communication.  For more
    information, see :doc:`architecture/rest_api`.

  Sawtooth core
    Central Sawtooth software that is responsible for message handling,
    block validation and publishing, consensus, and global state management.
    The Sawtooth architecture separates these core functions from
    application-specific business logic, which is is handled by
    transaction families.

  Sawtooth network
    Peer-to-peer network of nodes running a validator (and associated
    components) that are working on the same blockchain.

  settings
    Sample transaction family that provides a reference implementation for
    storing on-chain configuration settings. For more information, see
    :doc:`transaction_family_specifications/settings_transaction_family`.

  state
    See :term:`global state`.

  state delta
    Result of a single change for a specific address in global state.

  state delta subscriber
    Client framework that subscribes to a validator for state deltas (changes)
    for a specific set of transaction families. Usually, an application
    subscribes to state deltas for the purpose of off-chain storage or action,
    such as handling the failure of a transaction appropriately.

  transaction
    Function that changes the state of the blockchain. Each transaction is put
    into a Batch, either alone or with other related transactions, then sent to
    the validator for processing.  For more information, see
    :doc:`architecture/transactions_and_batches`.

  transaction family
    Application-specific business logic that defines a set of operations or
    transaction types that are allowed on the blockchain. Sawtooth transaction
    families separate the transaction rules and content from the Sawtooth core
    functionality.

    A transaction family implements a data model and transaction language for
    an application. Sawtooth includes example transaction families in several
    languages, such as Python, Go, and Java.  For more information, see
    :ref:`sample-transaction-families-label`.

  transaction processor
    Validates transactions and updates state based on the rules defined by the
    associated transaction family. Sawtooth includes transaction processors for
    the sample transaction families, such as ``identity-tp`` for the Identity
    transaction family. For more information, see
    :doc:`transaction_family_specifications`.

  validator
    Component responsible for validating batches of transactions, combining
    them into blocks, maintaining consensus with the Sawtooth network,
    and coordinating communication between clients, transaction processors, and
    other validators on the network.

  validator node
    See :term:`node`.

  XO
    Sample transaction family that demonstrates basic transactions by playing
    `tic-tac-toe <https://en.wikipedia.org/wiki/Tic-tac-toe>`__ on the
    blockchain. For more information, see
    :doc:`transaction_family_specifications/xo_transaction_family`.

.. |Intel (R)| unicode:: Intel U+00AE .. registered copyright symbol

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

Glossary
========

This glossary defines general Sawtooth terms and concepts.

.. glossary::

  Batch
    Group of related transactions.
    In Sawtooth, a batch is the atomic unit of state change for the blockchain.
    A batch can contain one or more transactions. For a batch with multiple
    transactions, if one transaction fails, all transactions in that batch fail.
    (The client application is responsible for handling failure appropriately.)
    For more information, see :doc:`architecture/transactions_and_batches`.

  Blockchain
    Distributed ledger that records transactions, in chronological order,
    shared by all participants in a Sawtooth network. Each block on the
    blockchain is linked by a cryptographic hash to the previous block.

  Consensus
    Process of building agreement among a group of mutually distrusting
    participants (other nodes on a Sawtooth network). Sawtooth allows
    different types of consensus on the same blockchain.
    See also :term:`Dynamic consensus`.

  Core
    See :term:`Sawtooth core`.

  Distributed ledger
    See :term:`Blockchain`.

  Dynamic consensus
    Ability to change the blockchain consensus protocol for a running Sawtooth
    network. The current consensus is an on-chain setting, so it can be changed
    by submitting a transaction.  For more information, see
    :ref:`dynamic-consensus-label`.

  Genesis block
    First block on the blockchain. The genesis block initializes the
    Sawtooth network.

  Global state
    Database that stores a local (validator-specific) record of transactions for
    the blockchain. Sawtooth represents state in a single instance of a
    Merkle-Radix tree on each validator node.  For more information, see
    :doc:`architecture/global_state`.

  Identity
    Sample transaction family that handles on-chain permissions (settings
    stored on the blockchain) for transactor and validator keys. This
    transaction family demonstrates how to streamline managing identities
    for lists of public keys. For more information, see
    :doc:`transaction_family_specifications/identity_transaction_family`.

  IntegerKey
    Sample transaction family with only three operations (set, increment, and
    decrement) that can be used to test deployed ledgers. For more information,
    see :doc:`transaction_family_specifications/integerkey_transaction_family`.

  Journal
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

  Node
    Participant in Sawtooth network. Each node runs a single validator, a
    REST API, and one or more transaction processors.

  Off-chain setting
    Setting or value that is stored locally, rather than on the blockchain.

  On-chain setting
    Setting or value that is stored on the blockchain (also referred to as
    "in state") so that all participants on the network can access that
    information.

  Permissioned network
    Restricted network of Sawtooth nodes. A permissioned network
    typically includes multiple parties with a mutual interest but without
    the mutual trust found in a network controlled by a single company or
    entity.

    The blockchain stores the settings that specify permissions, such as roles
    and identities, so that all participants in the network can access this
    information.

  PoET
    Proof of Elapsed Time, a Nakamoto-style consensus algorithm that is designed
    to support large networks. PoET relies on a Trusted Execution Environment
    (TEE) such as |Intel (R)| Software Guard Extensions (SGX).

    Sawtooth offers two version of PoET consensus. PoET-SGX relies on
    |Intel (R)| SGX to implement a leader-election lottery system. PoET
    simulator provides the same consensus algorithm on an SGX simulator.
    For more information, see :doc:`architecture/poet`.

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

  Settings
    Sample transaction family that provides a reference implementation for
    storing on-chain configuration settings. For more information, see
    :doc:`transaction_family_specifications/settings_transaction_family`.

  State
    See :term:`Global state`.

  State delta
    Result of a single change for a specific address in global state.

  State delta subscriber
    Client framework that subscribes to a validator for state deltas (changes)
    for a specific set of transaction families. Usually, an application
    subscribes to state deltas for the purpose of off-chain storage or action,
    such as handling the failure of a transaction appropriately.

  Transaction
    Function that changes the state of the blockchain. Each transaction is put
    into a Batch, either alone or with other related transactions, then sent to
    the validator for processing.  For more information, see
    :doc:`architecture/transactions_and_batches`.

  Transaction family
    Application-specific business logic that defines a set of operations or
    transaction types that are allowed on the blockchain. Sawtooth transaction
    families separate the transaction rules and content from the Sawtooth core
    functionality.

    A transaction family implements a data model and transaction language for
    an application. Sawtooth includes example transaction families in several
    languages, such as Python, Go, and Java.  For more information, see
    :ref:`sample-transaction-families-label`.

  Transaction processor
    Validates transactions and updates state based on the rules defined by the
    associated transaction family. Sawtooth includes transaction processors for
    the sample transaction families, such as ``identity-tp`` for the Identity
    transaction family. For more information, see
    :doc:`transaction_family_specifications`.

  Validator
    Component responsible for validating batches of transactions, combining
    them into blocks, maintaining consensus with the Sawtooth network,
    and coordinating communication between clients, transaction processors, and
    other validator nodes.

  XO
    Sample transaction family that demonstrates basic transactions by playing
    `tic-tac-toe <https://en.wikipedia.org/wiki/Tic-tac-toe>`_ on the
    blockchain. For more information, see
    :doc:`transaction_family_specifications/xo_transaction_family`.

.. |Intel (R)| unicode:: Intel U+00AE .. registered copyright symbol

.. Licensed under Creative Commons Attribution 4.0 International License
.. https://creativecommons.org/licenses/by/4.0/

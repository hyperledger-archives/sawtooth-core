********
Overview
********

The Distributed Ledger is Intel's proposed contribution to the
`Hyperledger Project <https://www.hyperledger.org/>`_ .


.. caution::

    This project includes a consensus algorithm, PoET (Proof
    of Elapsed Time), designed to run in a secure enclave like
    `Intel® Software Guard Extensions
    <https://software.intel.com/en-us/isa-extensions/intel-sgx>`_.
    The version included in this project is intended to provide
    the same functional characteristics, but runs **unprotected**.
    It does **not** provide security in this mode.  This project
    is intended for experimental usage. Do not use this project
    for security sensitive applications.


Features
=========

The Intel Ledger has several features:

- Supports multiple network topologies for the validator
  network. The default is a random walk topology. This project also
  includes an implementation of the Barabasi-Albert algorithm.

- Supports multiple distributed consensus algorithms.
  The default algorithm uses PoET but simulates
  execution in a secure enclave (see caution above).
  This project also includes a consensus algorithm for quorum voting.

- Supports unlimited asset classes, each with their own
  transactions, states, state transitions and state key-value store.
  Each transaction references the name of the asset class. The asset
  class name references the logic which is run to validate and process
  the transaction. Additional asset classes can easily be added.
  In the project, these asset classes are referred to as
  "Transaction Families".




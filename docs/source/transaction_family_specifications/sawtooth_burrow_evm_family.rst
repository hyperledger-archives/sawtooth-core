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

****************************************************
Sawtooth Burrow-EVM Transaction Family Specification
****************************************************

Overview
=========
The Sawtooth Burrow-EVM transaction family enables the creation and execution
of smart contracts within the Hyperledger Sawtooth framework. It integrates the
Hyperledger Burrow implementation of the Ethereum Virtual Machine (EVM) into
the Hyperledger Sawtooth framework using the Sawtooth Go SDK.

The primary problems to solve in order to integrate the Burrow EVM into
Sawtooth are:

1. Define and implement an efficient mapping between EVM World State addresses
   and Sawtooth Global State addresses.
2. Define and implement an efficient method for maintaining accounts and
   account storage in Sawtooth Global State.
3. Define and implement an “EVM-Wrapper” at the Transaction Processor level for
   handling additional “Ethereum-like” and “Burrow-like” features not
   implemented by the EVM, including:

    a. Handling account creation transactions and storing the resulting code in
       global state.
    b. Managing and enforcing account permissions.
    c. Maintaining account balances and transferring funds between accounts.
    d. Checking transaction nonces against account nonces and deriving new
       contract account addresses.

4. Define and implement an efficient API for:

    a. Submitting transactions to the network that load and execute EVM byte
       code in a way that is compatible with existing tools.
    b. Querying state using smart contracts without requiring that state be
       modified.

5. Define and implement an event subscription system for monitoring the EVM
   namespace that can be used with solidity events.

This spec assumes a basic knowledge of Ethereum, Hyperledger Burrow, and
Hyperledger Sawtooth.

For more information on Ethereum and the EVM, see the `Ethereum Yellow Paper`_.

.. _Ethereum Yellow Paper: https://ethereum.github.io/yellowpaper/paper.pdf

For more information on `Hyperledger Burrow`_, check out the project.

.. _Hyperledger Burrow: https://github.com/hyperledger/burrow

.. note::

    This is a proof of concept implementation that attempts to solve problems
    1, 2, and part of 3. Later versions of the spec will include solutions to
    the remaining problems including optimizations, handling permissions, event
    subscription, and incentives.

State
=====

Accounts
--------
State associated with the Sawtooth Burrow-EVM Transaction Family shall consist
of a set of accounts. Similar to Ethereum, two types of accounts shall be
defined:

* Externally Owned Accounts (EOAs)
* Contract Accounts (CAs)

EOAs are accounts that are owned by an external actor (ultimately a person).
They are created implicitly whenever a private key is generated. Upon
submission of the first transaction by an EOA, the account is initialized in
state.

CAs are created and owned by other accounts (either an EOA or another CA). All
CAs are ultimately associated with an EOA.

For more information on Ethereum Accounts, see the `Ethereum Documentation`_.

.. _Ethereum Documentation: http://ethdocs.org/en/latest/account-management.html#accounts

Account Storage Format
----------------------
Accounts and any associated account storage shall be stored in global state
using the following protobuf message format::

    message EvmEntry {
        EvmStateAccount account = 1;
        repeated EvmStorage storage = 2;
    }

    message EvmStateAccount {
        bytes address = 1;
        int64 balance = 2;
        bytes code = 3;
        int64 nonce = 4;
    }

    message EvmStorage {
        bytes key = 1;
        bytes value = 2;
    }

The following fields defined above shall be ignored for this version of the
spec, but will be used in later versions:

* balance - Since this version of the spec does not include an incentive system
  or associated cryptocurrency, maintaining a balance isn’t meaningful.

Addressing
==========

EVM Prefix
----------
All data associated with the Sawtooth Burrow-EVM Transaction Family shall be
stored under the prefix formed by taking the first 3 bytes of the SHA512 hash
of the UTF-8 encoded string “burrow-evm”. This shall be referred to as the EVM
prefix.::

    >>> hashlib.sha512('burrow-evm'.encode('utf-8')).hexdigest()[0:6]
    'a84eda'

Account Addresses
-----------------
The address of an account depends on which type of account it is:

* EOA - Given an EOA’s private key, the address is the, “rightmost 160-bits of
  the Keccak hash of the corresponding ECDSA public key,” from the yellow paper.
  The “Keccak hash” shall be taken to mean SHA3.
* CA - The address of a CA is the last 20 bytes of the 256-byte SHA3 hash of
  the byte array formed by concatenating the sender address and the big endian
  encoding of the sender’s current nonce. In other words, the address of a CA is
  derived from hashing the creating accounts address and its nonce.

Accounts in the above format shall be stored in global state at the address
formed by concatenating the EVM prefix, address of the account, and enough 0’s
to form a valid global state address.::

    >>> state_address = 'a84eda' + account_address + '0'*12

Transaction Payload
===================

The transaction payload closely follows the structure as defined by the EVM
yellow paper, section 4.3 (“The Transaction”). In the Sawtooth Burrow-EVM
Transaction Family, the transaction payload shall be represented using the
following protobuf message::

    message EvmTransaction {
        // "...the number of transactions sent by the sender; formally T_n."
        uint64 nonce = 1;

        // "...the number of Wei to be paid per unit of gas for all computation
        // costs incurred as a result of the execution of this transaction;
        // formally T_p."
        uint64 gas_price = 2;

        // "...the maximum amount of gas that should be used in executing this
        // transaction. This is paid up-front, before any computation is done and
        // may not be increased later; formally T_g"
        uint64 gas_limit = 3;

        // "...the 160-bit address of the message call's recipient or, for a
        // contract creation transaction, {}, used here to denote (the empty byte
        // array); formally T_t."
        bytes to = 4;

        // "...the number of Wei to be transferred to the message call's recipient
        // or, in the case of contract creation, as an endowment to the newly
        // created account; formally T_v."
        uint64 value = 5;

        // The yellow paper also includes a signature in the transaction, but this
        // is already included as part of the Sawtooth transaction so we don't
        // duplicate it here.

        // "An unlimited size byte array specifying the EVM-code for the account
        // initialisation procedure, formally T_i."
        //
        // This should only be set if this is a contract creation transaction.
        bytes init = 7;

        // "An unlimited size byte array specifying the input data of the message
        // call, formally T_d."
        //
        // This should only be set if this is a message call transaction.
        bytes data = 8;
    }

The following fields defined above shall be ignored for this version of the
spec, but will be used in later versions:

* gas_price - Since this version of the spec does not include an incentive
  system or account balances, a gas_price is not meaningful since there is
  nothing to purchase gas with. Instead, the client supplied gas_limit will
  serve to limit the amount of gas used by a given transaction.
* value - Since this version of the spec does not include an incentive system
  or account balances, transferring value between accounts is not meaningful.

Execution
=========

Transaction execution shall follow a simplified version of the Ethereum model
described below:

1. The sender address shall be calculated by taking the rightmost 160 bits of
   the SHA3 hash of the public key used to submit the transaction. This public
   key is included in the transaction header.
2. If the `to` field is set, the transaction is interpreted as a “message call”
   transaction. If not, it is a “contract creation” transaction.
3. If the transaction is a “message call” transaction,

    a. The receiver’s account will be retrieved from state using the address in
       the `to` field. If the address is invalid, the account does not exist, or
       the account does not contain any code, the transaction is invalid.
    b. The sender’s account will be retrieved from state using the sender
       address. If the account does not exist, the transaction is invalid.
    c. The EVM will be called using:

        - The sender account for the `caller` argument
        - The receiver account for the `callee` argument
        - The `code` field in the receiver’s account for the `code` argument
        - The `data` field in the transaction payload for the `input` argument.
          If no data field is set, the transaction is invalid.
        - 0 for the `value` argument.
        - The `gas_limit` field in the transaction payload for the `gas`
          argument.

    d. The resulting output from the EVM shall be discarded because a mechanism
       for returning data to the client does not exist yet.
    e. The sender and receiver accounts and associated storage shall be pushed
       to state.

4. If the transaction is a “contract creation” transaction,

    a. If the sender address does not exist yet, an Externally Owned Account
       shall be created at the address.
    b. If the sender address does exist, a Contract Account shall be created at
       a new address derived from the sender account as described above. The
       sender account’s nonce shall then be incremented.
    c. If the `init` field is set in the transaction payload, the EVM will be
       called using:

        - The sender account for the `caller` and `callee` arguments
        - The `init` field for the `code` argument
        - `nil` for the `input` argument.
        - 0 for the `value` argument.
        - The `gas_limit` field in the transaction payload for the `gas`
          argument.

    d. The resulting output from the EVM shall be stored in the `code` field of
       the newly created account.
    e. The sender account and the newly created account shall be pushed to
       state.

5. If an error occurs while the EVM is executing, the transaction is invalid.

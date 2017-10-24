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

****************
Developing DApps
****************

.. TODO:
    [ ] Lookup nonce when sending a transaction

Starting Seth RPC
=================

In order to develop full-stack applications with Seth, we need a way to
programatically interact with Seth. Sawtooth provides a general-purpose REST
API for submitting queries about the network and generic transactions that
could be used for this. However, this would require a complete understanding of
the :doc:`Seth Transaction Family Spec <seth_transaction_family_spec>`. Instead,
Seth comes with a web server that implements much of the `Ethereum JSON-RPC
API`_, the :ref:`seth-rpc <seth-rpc-reference-label>` server. This interface
provides a much higher level interface for developing Seth applications and is
the recommended interface.

.. _Ethereum JSON-RPC API: https://github.com/ethereum/wiki/wiki/JSON-RPC

The ``seth-rpc`` server accepts HTTP POST requests from clients, communicates
with a sawtooth-validator to fulfill the request, and then responds with the
appropriate output. This means you must have a running validator for it to
connect to.

First, start a validator and confirm that is is running, as described in
:doc:`Getting Started<getting_started>`. Next, you can start the ``seth-rpc``
server from the seth container with::

  $ seth-rpc --connect tcp://validator:4004 --bind 0.0.0.0:3030

This will start the server which will begin listening for requests.

.. warning::

  You should only bind seth-rpc to 0.0.0.0 for development purposes as it starts
  listening for requests on all interfaces. This is a potential security risk in
  production environments.

You can now submit requests to the server. If you are using the docker-compose
environment described earlier, port 3030 in the seth container should be
forwarded to your host's port, so you can send requests from your host. For
example, you can get the current block number by running curl from a prompt on
your host with::

  $ curl -d '{"jsonrpc": "2.0", "method": "eth_blockNumber", "id": 1}' -H "Content-Type: application/json" localhost:3030

Deploying Contracts
===================

Contracts can also be deployed using the ``seth-rpc`` server. In order to
submit any requests that reference specific accounts, that account must be
unlocked when ``seth-rpc`` is started. Only external accounts that have been
imported with the ``seth`` client may be unlocked by the ``seth-rpc`` server.

To unlock an account when starting ``seth-rpc`` pass the ``--unlock`` flag and
the alias of the account to unlock::

  $ seth-rpc --unlock {alias}

To deploy a contract using the unlocked account, you must know its address. If
you do not already know the address, you can get it with ``seth account list``.
Once you have the account address, you can deploy a contract through the
``seth-rpc`` server with the ``eth_sendTransaction`` method::

  $ curl -d '{"jsonrpc": "2.0", "method": "eth_sendTransaction", "id": 2, "params": [{"from": "0x{address}", "data": "0x{contract}"}]}' -H "Content-Type: application/json" localhost:3030

You should substitute ``{address}`` with the address of the unlocked account and
``{contract}`` with the contract deployment code. The return value of this call
is the id of the contract creation transaction with a ``0x`` prefix. You can use
this id to get the result of the contract creation transaction with
``eth_getTransactionReceipt``::

  $ curl -d '{"jsonrpc": "2.0", "method": "eth_getTransactionReceipt", "id": 3, "params": [0x{transaction-id}}", "data": "0x{contract}"}]}' -H "Content-Type: application/json" localhost:3030

where ``{transaction-id}`` should  be substituted with the transaction id
returned by ``eth_sendTransaction``. The return value is a JSON object. If the
transaction was processed successfully, the object  will contain an
``"address"`` key that references the address of the newly created contract.

.. note::

  The ``eth_sendTransaction`` method is used for both contract creation and
  contract calls. If the parameters passed include a ``"to"`` key, then the
  transaction is treated as a contract call. Otherwise it is treated as a
  contract creation.

Calling Contracts
=================

Once a contract has been deployed, it can be called with the
``eth_sendTransaction`` method::

  $ curl -d '{"jsonrpc": "2.0", "method": "eth_sendTransaction", "id": 2, "params": [{"from": "0x{address}", "data": "0x{input}", "to": "0x{contract}"}]}' -H "Content-Type: application/json" localhost:3030

You should substitute ``{address}`` with the address of the unlocked account,
``{input}`` with the input data for the contract and ``{contract}`` with the
address of the deployed contract. The return value of this call is the id of the
contract call transaction, which can be used with the
``eth_getTransactionReceipt`` method to get the result of the transaction.

Subscribing to Logs
===================

Logs that are generated by contracts, such as Solidity contracts that define and
call any ``event`` types, can be subscribed to with the ``eth_newFilter``
method. More information on how to subscribe to logs generated by Solidity can
be found in the `Solidity Documentation on Events`_.

.. _Solidity Documentation on Events: https://solidity.readthedocs.io/en/develop/abi-spec.html#events

External Libraries
==================

The ``seth-rpc`` server implements many of the methods defined by the `Ethereum
JSON-RPC API`_. There are several libraries and tools for building applications
that depend on this interface, such as `Web3 JS`_ and `Truffle`_, and it should
be possible to use parts of these libraries with ``seth-rpc``.

.. _Web3 JS: https://www.npmjs.com/package/web3
.. _Truffle: http://truffleframework.com/

As of this writing, compatibility these libraries has not been tested in any
way. Help with testing and improving compatibility with these libraries is
welcome, including sharing information about how the ``seth-rpc`` server is
being used, submitting issues that are encountered, and submitting pull requests
that improve the ``seth-rpc`` server's compatibility with these libraries.

Supported Ethereum JSON-RPC API Methods
=======================================

Compatibility Notes
-------------------

When requesting block objects by hash, the block hash must be 64 bytes instead
of 32 bytes.

When returning block objects, the following fields always have the zero value,
since they do not have a corollary in Sawtooth:

* "nonce"
* "sha3Uncles"
* "logsBloom"
* "transactionsRoot"
* "receiptsRoot"
* "miner"
* "difficulty"
* "totalDifficulty"
* "extraData"
* "size"
* "gasLimit"
* "uncles"

When returning receipt objects, "cumulativeGasUsed" is always 0.

When returning log objects, "logIndex" is always 0 and "removed" is always
false.

Method List
-----------

The following JSON-RPC calls are supported. See the `Ethereum JSON-RPC API`_
spec for details on parameters and return values.

+----------------------------------------+---------+---------------------------+
| Method                                 | Support | Additional Notes          |
+========================================+=========+===========================+
| eth_accounts                           |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_blockNumber                        |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_gasPrice                           | Partial | Always returns 0          |
+----------------------------------------+---------+---------------------------+
| eth_getBalance                         |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getBlockByHash                     | Partial |                           |
+----------------------------------------+---------+---------------------------+
| eth_getBlockByNumber                   |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getBlockTransactionCountByHash     |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getBlockTransactionCountByNumber   |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getCode                            |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getFilterChanges                   | Partial | For pending transaction   |
|                                        |         | filters, transactions that|
|                                        |         | committed transactoins are|
|                                        |         | returned instead.         |
+----------------------------------------+---------+---------------------------+
| eth_getFilterLogs                      |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getLogs                            |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getStorageAt                       |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getTransactionByBlockHashAndIndex  |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getTransactionByBlockNumberAndIndex|  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getTransactionByHash               |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getTransactionCount                |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_getTransactionReceipt              |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_newBlockFilter                     |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_newFilter                          |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_newPendingTransactionFilter        |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_sendTransaction                    |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_sign                               |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| eth_uninstallFilter                    |  Full   |                           |
+----------------------------------------+---------+---------------------------+
| net_listening                          | Partial | Always returns true       |
+----------------------------------------+---------+---------------------------+
| net_peerCount                          | Partial | Always returns 0          |
+----------------------------------------+---------+---------------------------+
| net_version                            | Partial | Always returns 19         |
+----------------------------------------+---------+---------------------------+

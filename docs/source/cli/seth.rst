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

.. _seth-cli-reference-label:

********
Seth CLI
********

Overview
========

The seth command can be used to interact with the Sawtooth Burrow-EVM
transaction family. It provides functionality for loading and executing smart
contracts, querying the data associated with a contract, and generating keys in
the format used by the tool. The following section reproduces the CLI usage
output obtained by running seth and its various subcommands with the `-h` flag.

See the final section for an explanation of how to generate contract
initialization data and how to format function calls using the Ethereum
Contract ABI.

seth
----

.. literalinclude:: output/seth_usage.out
   :language: console
   :linenos:

seth create
-----------

.. literalinclude:: output/seth_create_usage.out
   :language: console
   :linenos:

seth exec
---------

.. literalinclude:: output/seth_exec_usage.out
   :language: console
   :linenos:

seth load
---------

.. literalinclude:: output/seth_load_usage.out
   :language: console
   :linenos:

seth show
---------

.. literalinclude:: output/seth_show_usage.out
   :language: console
   :linenos:

Compiling Contracts
===================

The `seth load` command has a `--init` flag which takes a hex-encoded
byte array as an argument. This string is interpreted as the contract creation
code. To generate this string given a Solidity smart contract, the `solc`
compiler can be used. Assuming the contract is named `contract.sol`, the
command is:

.. code-block:: console

    $ solc --bin contract.sol

    ======= contract.sol:SimpleStorage =======
    Binary:
    6060604052341561000c57fe5b5b60c68061001b6000396000f30060606040526000357c0100000000000000000000000000000000000000000000000000000000900463ffffffff16806360fe47b11460445780636d4ce63c146061575bfe5b3415604b57fe5b605f60048080359060200190919050506084565b005b3415606857fe5b606e608f565b6040518082815260200191505060405180910390f35b806000819055505b50565b600060005490505b905600a165627a7a7230582042f71fb995ac3f6a4ce0560bae1342e5a54e96ec0462f812340a305e3c94da910029

The hex string that is output by this command can be passed directly to the
`--init` flag.

For more information on solc including how to install it and more advanced
usage, read the `Solidity Documentation`_.

.. _Solidity Documentation: https://solidity.readthedocs.io/en/develop/index.html

ABI Formatting
==============

The `seth exec` command has a `--data` flag which takes a hex-encoded byte
array as an argument. This string is interpreted according to the Ethereum
Contract ABI and, in the context of solidity, is used to select a function and
pass in arguments to that function.

One option for generating this string given a Solidity function is to use the
`ethereumjs-abi`_ library.

.. _ethereumjs-abi: https://www.npmjs.com/package/ethereumjs-abi

Given the solidity function `set(uint key, uint val) {...}` and the specific
call `set(19, 84)`, the commands to generate the byte array are:

.. code-block:: console

    $ node
    > var abi = require('ethereumjs-abi')
    > abi.simpleEncode("set(uint,uint)", "0x13", "0x54").toString("hex")
    '1ab06ee500000000000000000000000000000000000000000000000000000000000000130000000000000000000000000000000000000000000000000000000000000054'

The hex string that is output by this command can be passed directly to the
`--data` flag.

For more information on the `Ethereum Contract ABI`_, read the wiki.

.. _Ethereum Contract ABI: https://github.com/ethereum/wiki/wiki/Ethereum-Contract-ABI

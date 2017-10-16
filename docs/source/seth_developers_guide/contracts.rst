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

*********
Contracts
*********

Once you have an account created, you can use it to deploy EVM smart contracts.
To demonstrate how to deploy and call contracts, we will be using the following
Solidity contract, which is based loosely on the IntegerKey Transaction Family.
`Solidity`_ is a high-level language for defining contracts that compiles to EVM
byte code for deployment. To follow along with this guide, you should create a
new file with this contract::

    pragma solidity ^0.4.0;

    contract intkey {
      mapping (uint => uint) intmap;

      event Set(uint key, uint value);

      function set(uint key, uint value) {
        intmap[key] = value;
        Set(key, value);
      }

      function inc(uint key){
        intmap[key] = intmap[key] + 1;
      }

      function dec(uint key){
        intmap[key] = intmap[key] - 1;
      }

      function get(uint key) constant returns (uint retVal) {
        return intmap[key];
      }
    }

.. _Solidity: https://solidity.readthedocs.io/en/develop/

Save this contract in a file called "contract.sol" in your working directory. If
you are working with the development environment described in
:doc`./getting_started` you should save this file in the sawtooth-core/
directory on your host so that it is available within the seth container.

Compiling Contracts
===================

Before we can deploy this contract, we have to compile it. The ``seth`` client
expects that the contract will be passed as a hex-encoded byte array. We can use
the Solidity compiler ``solc`` to create it. If you followed the
:doc:`./getting_started` instructions, this tool is already installed in the
seth container we created earlier. Connect to the seth container as explained
there. If not, we assume you have it installed locally.

To compile the contract, run::

    $ solc --bin contract.sol

    ======= contract.sol:intkey =======
    Binary:
    ...byte array here...

Save the blob of hex-encoded bytes somewhere as we are going to use it in the
next step.

Deploying Contracts
===================

Now that we have an account and a compiled contract, we can deploy the contract
with::

    $ seth contract create --wait myalias {contract}

In place of ``{contract}`` you should insert the blob of hex that you saved from
earlier. This will create a new contract creation transaction and submit it to
the validator.

If everything works, a new contract account will be created and the client will
print the address of the newly created contract account along with some
additional execution information. To confirm the contract was deployed, you can
run::

    $ seth show account {address}

You will notice that the above command uses the argument ``address``, not
``contract``. This is because an account is short for "external account" and a
contract is short for "contract account."  That is, they are actually both
accounts, but a contract account is an account with a contract that is owned by
another account.

.. note::

  If you lose the address of your contract, you can get a list of the addresses
  that would have been derived for your contract based on the nonce of the
  account used to create it with ``seth contract list {alias}``. For more info,
  see the beginning of `Ethereum Quirks and Vulns`_.

.. _Ethereum Quirks and Vulns: http://martin.swende.se/blog/Ethereum_quirks_and_vulns.html

Calling Contracts
=================

To call the deployed contract we need the address where the contract is deployed
and the input data for the contract call. The address was printed when the
contract was deployed. Constructing the input for the contract is a little
harder.

Solidity uses an `Application Binary Interface`_ or ABI to determine which
function in your contract to run and what the function call's arguments are.
There are many tools available for abstracting the creation of the input data
for a contract call. One option for generating the input data that is compatible
with the ``seth`` client is the `ethereumjs-abi`_ library. If you are using the
development environment described earlier, this is already installed in the seth
docker container.

.. _Application Binary Interface: https://solidity.readthedocs.io/en/develop/abi-spec.html
.. _ethereumjs-abi: https://www.npmjs.com/package/ethereumjs-abi

To use this library to call a function in contract, you can use the
``simpleEncode``. The following shows how to call the ``set()`` function in the
contract we deployed earlier with arguments ``19`` and ``42``::

    $ node
    > var abi = require('ethereumjs-abi')
    > abi.simpleEncode("set(uint,uint)", "0x13", "0x2a").toString("hex")
    ...byte array here...

To call our contract and run ``set(19,42)``, run::

    $ seth contract call --wait {address} {input}

In place of ``{input]`` you should insert the blob of hex formatted according to
the contract's ABI that we created above. If everything works, the client will
state that transaction was succesful and print the transaction id. To verify
that the message call was successful, you can do::

    $ seth show receipt {transaction-id}

In place of ``{transaction-id}`` you should insert the id that was printed out
after calling the contract.

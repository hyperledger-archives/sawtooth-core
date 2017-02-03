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


********************************************
Sawtooth Lake Bond Family Workload Simulator
********************************************

Sawtooth Lake has a workload simulator that can be used to generate a
synthetic transaction workload.  General information about synthetic
workload generation can be found in the workload simulator section of
the Sawtooth Lake Developer's Guide.  The workload simulator relies upon
a workload generator to generate transactions for a particular transaction
family.  The Sawtooth Lake project includes a workload generator
that the workload simulator uses to generate a synthetic bond transaction
workload (quotes and buy/sell orders).

Overview of the Bond Transaction Workload Operation
---------------------------------------------------

Upon startup, the workload simulator discovers the initial validator network.
For each validator discovered, the bond workload generator submits
transactions to that validator to:

* Create a participant that will be referenced as the authorizing participant
  when the organizations that create quote and order transactions are created.
  Synthetic participants can be distinguished by their names, which consist of
  ``P_`` followed by a string of 14 random hexadecimal digits (0-9a-f).
* Create a trader organization that will create order
  transactions.  Synthetic traders can be distinguished by their names,
  which consist of ``T_`` followed by the same 14 random hexadecimal digits
  that appear in the creating participant's name.
* Create a market maker organization that will create quote transactions.
  Synthetic market makers can be distinguished by their names,
  which consist of ``M_`` followed by the same 14 random hexadecimal digits
  that appear in the creating participant's name.  In addition to a unique
  name, market makers also have a unique pricing source, which consists
  of the captial letter Z followed by three lower and/or upper case letters.

After the initial validator network is discovered, and prior to the generation
of the synthetic transaction workload, if the configuration file references
a setup file (see :ref:`configuring-the-bond-workload-generator-label`), the
bond workload generator will perform any setup (creating participants,
organizations, bond, quotes, etc.) specified in the setup file.  In order to
ensure that the validator network is in a consistent state after the setup
file transactions have been submitted, the bond workload generator waits until
all validators in the validator network have committed the setup file
transactions to their blockchains.

As a final step before synthetic workload generation, the bond workload
generator discovers, via the validator network, the list of bonds that will
be used later by traders and market makers when creating order and quote
transactions, respectively.

Once the setup is completed, at, or as close as possible to, the rate
specified either on the command-line or in the simulator configuration file,
the bond workload generator will generate either an order or a quote
transaction, dictated by the ratio of order to quote transactions (see
:ref:`configuring-the-bond-workload-generator-label`).  For each transaction,
the bond workload generator will pick a random bond from the list of bonds
discovered previously and a random validator (and therefore, by
association its trader or market maker organization) to which the transaction
will be submitted.

For order transactions, the bond workload generator:

* Randomly chooses to either buy or sell the bond chosen.
* Randomly chooses a quantity between 1,000 and 10,000, inclusive, in
  multiples of 1,000.
* Sets the order type to market.

For quote transactions, the bond workload generator:

* Randomly chooses a bid price between 100-00 0/8 and 105-31 7/8,
  inclusive.
* Randomly chooses a bid quantity between 100,000 and 500,000, inclusive, in
  multiples of 1,000.
* Randomly chooses an ask price between the bid prices and 105-31 7/8,
  inclusive.
* Randomly chooses an ask quantity between 100,000 and 500,000, inclusive, in
  multiples of 1,000.

Configuring the Simulator to Generate a Bond Workload
-----------------------------------------------------

To generate a synthetic bond transaction workload, the workload simulator
needs to be configured to use the bond workload generator,
``sawtooth_bond.bond_workload.BondWorkload``.  This can be done
in one of two ways:

* Use the workload simulator's ``--workload`` command-line option:

    .. code-block:: console

        $ cd /project/sawtooth-core
        $ ./bin/simulator --workload sawtooth_bond.bond_workload.BondWorkload

* Edit the workload simulator configuration file and in the ``[Simulator]``
  section, set the workload configuration option:

    .. code-block:: console

        [Simulator]
        workload = sawtooth_bond.bond_workload.BondWorkload

In either case, when the simulator starts, it should indicate that it is using
the bond workload generator:

.. code-block:: console

    [22:59:19 INFO    simulator_cli] Simulator configuration:
    [22:59:19 INFO    simulator_cli] Simulator: url = http://127.0.0.1:8800
    [22:59:19 INFO    simulator_cli] Simulator: workload = sawtooth_bond.bond_workload.BondWorkload
    [22:59:19 INFO    simulator_cli] Simulator: rate = 12
    [22:59:19 INFO    simulator_cli] Simulator: discover = 15
    [22:59:19 INFO    simulator_cli] Simulator: verbose = 1

.. _configuring-the-bond-workload-generator-label:

Configuring the Bond Workload Generator
---------------------------------------

The bond workload generator is configured using the same configuration
file used to configure the workload simulator.  All bond workload
configuration options must appear in a section named ``[BondWorkload]``.  A
sample simulator configuration file,
``extensions/bond/sawtooth_bond/bond_workload_sample.cfg``, with a bond workload
generator section is provided and its contents are similar to the following:

.. code-block:: console

    [Simulator]
    url = http://127.0.0.1:8800
    workload = sawtooth_bond.bond_workload.BondWorkload
    rate = 20
    discover = 15
    verbose = 1

    [BondWorkload]
    setup_file = /project/sawtooth-core/extensions/bond/data/bond_workload_sample_setup.yaml
    order_to_quote_ratio = 15

The ``[Simulator]`` section configuration options are described in detail in
the simulator workload section of the Sawtooth Lake Developer's Guide.

The ``[BondWorkload]`` section may contain the following configuration options:

* ``setup_file`` The file used to set up the validator network prior to the
  generation of the synthetic bond transaction workload.  The setup file is
  expressed in YAML and follows the same format as the file that the bond
  transaction family command-line interface load command (see
  :ref:`btp-cli-reference-label`).  A sample setup file can be found in
  ``sawtooth-core/extensions/bond/data/bond_workload_sample_setup.yaml``.
  If this option does not appear in the configuration file, then validator
  network setup is skipped.If there are any errors in the setup transactions,
  the bond workload generator will log a warning, but will continue.
* ``order_to_quote_ratio`` The number of order transactions to create for each
  quote transaction created.  Note that this is simply a ratio of order
  transactions to quote transactions and there is no attempt to correlate or
  match up the transactions.  In the example configuration file above, for
  every fifteen order transactions that the bond workload generator
  creates it creates one quote transaction.  If this option does not appear
  in the configuration file, the default order to quote ratio is ten.

***
FAQ
***

Validators
==========


How do I change the validator configuration?
--------------------------------------------

The default configuration file is at
`sawtooth-validator/etc/txnvalidator.js`. We recommend you copy that
file to a new file in the same directory and make changes to the new file.
When starting the txnvalidator, use the `--config` argument to reference
the configuration file, In this example, we have copied the
`txnvalidator.js` file to `single-node.js` and modified it:

.. code-block:: console

    $ cd /project/sawtooth-validator
    $ ./bin/txnvalidator -v --config ../etc/single-node.js

Multiple config files can be overlaid, and all of the settings in the
config file can be overridden on the command line, but that's beyond the
scope of this answer.

What configuration changes should I make to run a single validator?
-------------------------------------------------------------------

Copy the `sawtooth-validator/etc/txnvalidator.js` to `single-node.js` and
make the following changes:


`TargetWaitTime`
The desired mean inter-block commit time across the network.
While the default is 30 seconds, we recommend 5 seconds for
development and experimenting.

`InitialWaitTime`
This is only important when starting the first node which
will initialize the ledger (i.e. `GenesisLedger` is true).
This will often be the case when testing. We recommend setting
it to the same value as `TargetWaitTime`.

******************************
Example Transaction Processors
******************************

Sawtooth includes several transaction families as examples for developing a
transaction processor. The following executables are available:

* ``block-info-tp`` - BlockInfo transaction processor, written in Python

* ``identity-tp`` - Identity transaction processor, written in Python

* ``intkey-tp-go`` - IntegerKey transaction processor, written in Go

* ``intkey-tp-java`` - IntegerKey transaction processor, written in Java

* ``intkey-tp-javascript`` - IntegerKey transaction processor, written in
  JavaScript (Node.js)

* ``intkey-tp-python`` - IntegerKey transaction processor, written in Python

* ``poet-validator-registry-tp`` - Validator Registry transaction processor,
  which is used by the PoET consensus algorithm implementation to keep track of
  other validators

* ``settings-tp`` - Settings family transaction processor, written in Python

  .. note::

    In a production environment, you should always run a transaction processor
    that supports the Settings transaction family.

* ``smallbank-tp`` - Smallbank transaction processor, written in Go

* ``xo-tp-javascript`` - XO transaction processor, written in JavaScript
  (Node.js)

* ``xo-tp-python`` - XO transaction processor, written in Python

See :doc:`/transaction_family_specifications` for more information on each
transaction processor.

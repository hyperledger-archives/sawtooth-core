
Sawtooth Lake Arcade
====================

This repository contains example code, in the form of games, which demonstrate
key concepts of Sawtooth Lake.

The documentation for Sawtooth Lake is available at:

  http://intelledger.github.io/

Sawtooth Tac Toe
----------------

Sawtooth Tac Toe contains two components:

  - A transaction family, sawtooth\_xo, which implements game rules
  - A client, xo, and client-side library code

The primary purpose of this game is to provide a simple transaction family
implementation which demonstrates the APIs available in sawtooth-core.

To use the sawtooth\_xo transaction family, it must be added to the list of
transaction families in txnvalidator.js:

```javascript
     "TransactionFamilies" : [
        "sawtooth_xo"
     ],
```

txnvalidator must be able to find the sawtooth_xo transaction family
implementation, which can be done by adding this repository directory to the
PYTHONPATH environment variable.


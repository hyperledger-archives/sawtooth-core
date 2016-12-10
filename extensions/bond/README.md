#Sawtooth Lake Bond Implementation

This extension contains an implementation of a transaction family which
enables a proof-of-concept bond trading platform, built on the Sawtooth Lake
distributed ledger. It also contains a command line interface and browser
based interface for interacting with the bond market. Real-world bond trading,
clearing, and settlement is significantly complex, so we have attempted to
select a core set of functionality that demonstrates how these platforms might
be built on blockchain technology. Further investment would be required to
move these concepts into production.


## Usage

Detailed instructions for running Sawtooth Lake validators can be found at
http://intelledger.github.io/. To add the bond trading transaction family to
your validator, modify its `txnvalidator.js` config file so that the
*Transaction Families* section looks like this:

```javascript
  "TransactionFamilies" : [
      "ledger.transaction.integer_key",
      "sawtooth_bond"
  ],
```

Further documentation on how to run individual parts of this extension (like
the browser UI), can be found in the Readmes in their individual directories.

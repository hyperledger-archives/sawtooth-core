3. (optional) Encode the Transaction(s)
---------------------------------------

If serializing your Transaction(s) to be sent to an external batcher, the Sawtooth SDK offers two options. One or more Transactions can be combined using the *encode* method, or if only serializing a single Transaction, creation and encoding can be combined into a single step with *createEncoded*.

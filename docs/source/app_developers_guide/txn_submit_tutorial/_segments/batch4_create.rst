.. note::

   The *batcher pubkey* specified in every TransactionHeader must have been generated from the private key being used to sign the Batch, or validation will fail.


4. Create the Batch
-------------------

Creating a Batch also looks a lot like creating a Transaction. Just use the compiled *Batch* class to instaniate a new Batch with the proper data.

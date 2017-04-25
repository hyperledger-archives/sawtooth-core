Building the Batch
==================

Once you have one or more Transaction instances ready, they must be wrapped in a *Batch*. Remember that the Batches are the atomic unit of change in Sawtooth's state. When a Batch is submitted to a validator each Transaction in it will be applied (in order), or *no* Transactions will be applied. Even if your Transactions are not dependent on any others, they cannot be submitted directly to the validator. They must all be wrapped in a Batch.
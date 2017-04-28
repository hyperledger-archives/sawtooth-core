3. Encode the Batch(es) in a BatchList
--------------------------------------

Like the TransactionEncoder, BatchEncoders have both *encode* and *createEncoded* methods for serializing Batches in a BatchList. If encoding multiple Batches in one BatchList, they must be created individually first, and then encoded. If only wrapping one Batch per BatchList, creating and encoding can happen in one step.

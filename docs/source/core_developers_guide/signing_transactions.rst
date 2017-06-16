-----------------------------------------------------------------
Signing Transactions
-----------------------------------------------------------------

Consistency in transaction signing is critical for successful submission
of transactions to Sawtooth.

**Step 1: Serialize the transaction**

The transaction schema describes the fields that must be present in the
serialized transaction. All fields, including optional fields, must have a
value set. For optional fields that are not specified, the value of the
field must be set to the default value specified in the schema.

The exception to the previous rule is that the top level "Signature"
field must be removed from the transaction completely. It is not
sufficient simply to set the value to an empty string.

An important note is that data types must match those used in the
schema. Specifically, a float must have at least one decimal point or
the value will be encoded as an integer. For example, for signing
purposes, 1.0 is not equivalent to 1.

All strings in the transaction including fields names and values should
be encoded as Unicode.

Fields in the transaction must be ordered alpha-numerically by field
name. This includes field in any contained object.

The transaction is serialized in `CBOR <http://cbor.io>`.

**Step 2: Create the signature for the serialized transaction**

The resulting serialized document is signed with the transactor's private
ECDSA key using the secp256k1 curve.

The validator expects a 64 byte "compact" signature. (This is a concatenation
of the R and S fields of the signature. Some libraries will include an
additional header byte, recovery ID field, or provide DER encoded signatures.
Sawtooth will reject the signature if it is anything other than 64 bytes.)

**Step 3: Add the signature to the transaction**

Set the value of the "Signature" field to the 64 byte base64 encoded signature.

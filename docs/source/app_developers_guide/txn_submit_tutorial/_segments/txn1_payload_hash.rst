1. Create a SHA-512 Payload Hash
--------------------------------

However the payload was originally encoded, in order to confirm it has not been tampered with, a hash of it must be included within the Transaction's header. This hash should be created using the SHA-512 function, and then formatted as a hexadecimal string.

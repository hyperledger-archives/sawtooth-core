
## Notes

1. Since the rust sawtooth sdk isn't a published crate yet, you'll need
   to point the sawtooth-sdk dependency in your Cargo.toml to a local
   copy. See the Cargo.toml in this repo for formatting.

2. After taking a look at the example implemenations in other languages,
   I think it's probably more idiomatic NOT to define a type like 
   intkey_payload, even though that's the "rust-y" thing to do.
   However, this implementation is surely better if you actually have
   complicated business logic in either your CLI or TP. 

3. I made this a binary to fit in with the rest of the examples, but I
   them as a library so I'm not able to include my tests file,
   but most of this has test coverage except for the hyper parts.
   If anyone is knowledgeable in that area please add some unit tests
   so I can see the proper way to do that.

4. Thank you to the Sabre team; much of this was lifted from their CLI 
   implementation since I'm especially new to futures/tokio and the 
   Rust SDK documentation appears to be in early days.

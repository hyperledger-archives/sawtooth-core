
## Notes

1. Since the rust sawtooth sdk isn't a published crate yet, you'll need
   to point the sawtooth-sdk dependency in your Cargo.toml to a local
   copy. See the Cargo.toml in this repo for formatting.

2. After taking a look at the example implemenations in other languages,
   I think it's probably more idiomatic NOT to define a type like 
   intkey_payload, even though that's the "rust-y" thing to do.
   However, this implementation is surely better if you actually have
   complicated business logic in either your CLI or TP. 

3. I made this a binary to fit in with the rest of the examples, but
   use all the modules except main.rs as a library, so I'm unable
   to include my actual test suite. There is test coverage for the core
   functionality except for the Hyper parts since I'm not acquainted
   with testing Hyper/network components in rust. If anyone has
   experience in that area, please add some unit tests so I can 
   see how it's done.

4. Thank you to the Sabre team; much of this was lifted from their CLI 
   implementation since I'm especially new to futures/tokio and the 
   Rust SDK documentation appears to be in early days.

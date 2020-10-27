# Release Notes

## Changes in Sawtooth 1.2.6

### sawtooth-core:

  - Add context to the various EnvironmentErrors that can occur in the
    blockstore operations, in order to make debugging easier.
  - Reduce visibility of modules in validator library to crate-level
  - Enable IPv6 support in the validator
  - Support listening on an IPv6 address in REST API
  - Handle an error in sawtooth-cli when schema is invalid
  - Correct metric for "chain head moved"
  - Fix reading from length-delimited input in sawadm

### Documentation:

  - Add missing documentation about Rust SDK
  - Clarify consensus compatibility info
  - Fix typos and broken links

## Changes in Sawtooth 1.2.5

### sawtooth-core:
 - Fixed issue with decoding state values which caused the validator to crash
   when settings with long values were used. Add DecodedMerkleStateReader for
   state views. This reader provides the CBOR-decoded values to the rust
   implementations of StateView structs via a new implementation of the
   StateReader.
 - Add a justfile with build, clean, docker-build-doc, docker-lint, fix, lint
   and test targets. This is currently Rust-centric as it's the easiest to put
   into the justfile in a useful manner.
 - Add stable and experimental features to all crates.

### Documentation:
- Fix capitalization of glossary and glossary references.

## Changes in Sawtooth 1.2.4

### sawtooth-core:
- Enable heartbeats for all zmq connections. Before only validator to validator
  zmq connections had heartbeats however if a network sat idle long enough the
  zmq connection between components may disconnect.
- Fix timestamp check in block_info for catch up. This was previously fixed in
  python but was missed in the rust version.

## Changes in Sawtooth 1.2.3

### sawtooth-core:
- Support for raw transaction headers, as specified in [Sawtooth RFC #23](https://github.com/hyperledger/sawtooth-rfcs/blob/master/text/0023-raw-txn-header.md).
  This feature is backward compatible via the use of a protocol version indicator.
- All core transaction families are compatible with [Sawtooth Sabre release 0.4](https://sawtooth.hyperledger.org/docs/sabre/releases/0.4.0/).
- A new BlockManager has been implemented, as specified in [Sawtooth RFC #5](https://github.com/hyperledger/sawtooth-rfcs/pull/5).
  This new feature improves block management and helps remove a known race
  condition that can cause network nodes to fork.
- Several core transaction families have been rewritten in Rust: Settings,
  Identity, and BlockInfo.
- All SDKs are in separate repositories for improved build time and release
  scheduling. The following SDKs were moved to their own repositories in this
  release:
  - [Go](https://github.com/hyperledger/sawtooth-sdk-go)
  - [Python](https://github.com/hyperledger/sawtooth-sdk-python)
  - [Rust](https://github.com/hyperledger/sawtooth-sdk-rust)
- The [Devmode consensus](https://github.com/hyperledger/sawtooth-devmode)
  engine has been moved to a separate repository.
- Consensus support has been modified to improve compatibility with PBFT
  consensus.
- Cache performance has been improved for settings and identity state.
- Duplicate signature validations have been eliminated.
- Duplicate batches are now removed from the pending queue and candidate blocks.
- Transaction processors now receive a registration ACK before receiving
  transaction process requests.
- Long-lived futures are expired when awaiting network message replies.
- Logs now have fewer duplicate log messages.

### Documentation:
- Improved summary of the supported consensus algorithms: PBFT, PoET, Raft, and
  Devmode. See [Introduction](https://sawtooth.hyperledger.org/docs/core/releases/1.2.3/introduction.html).
- Complete procedures for configuring PBFT consensus on a Sawtooth node and
  changing network membership. For procedures to configure either PBFT or PoET
  consensus, see:
  - [Creating a Sawtooth Test Network](https://sawtooth.hyperledger.org/docs/core/releases/1.2.3/app_developers_guide/creating_sawtooth_network.html) (Application Developer’s Guide)
  - [Setting Up a Sawtooth Network](https://sawtooth.hyperledger.org/docs/core/releases/1.2.3/sysadmin_guide/setting_up_sawtooth_network.html) (System Administrator’s Guide)
- New Swift and Java tutorials, including SDK reference documentation, for
  writing native mobile client applications for Sawtooth. See the Java and Swift
  links in [Using the Sawtooth SDKs](https://sawtooth.hyperledger.org/docs/core/releases/1.2.3/app_developers_guide/using_the_sdks.html)
- Technical corrections, bug fixes, and general improvements throughout the
  documentation.

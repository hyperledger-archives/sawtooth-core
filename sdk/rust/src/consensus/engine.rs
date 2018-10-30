/*
 * Copyright 2018 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ------------------------------------------------------------------------------
 */

use std::error;
use std::fmt;
use std::sync::mpsc::Receiver;

use hex;

use consensus::service::Service;

/// An update from the validator
#[derive(Debug)]
pub enum Update {
    PeerConnected(PeerInfo),
    PeerDisconnected(PeerId),
    PeerMessage(PeerMessage, PeerId),
    BlockNew(Block),
    BlockValid(BlockId),
    BlockInvalid(BlockId),
    BlockCommit(BlockId),
    Shutdown,
}

pub type BlockId = Vec<u8>;

/// All information about a block that is relevant to consensus
#[derive(Clone, Default)]
pub struct Block {
    pub block_id: BlockId,
    pub previous_id: BlockId,
    pub signer_id: PeerId,
    pub block_num: u64,
    pub payload: Vec<u8>,
    pub summary: Vec<u8>,
}
impl fmt::Debug for Block {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(
            f,
            "Block(block_num: {:?}, block_id: {:?}, previous_id: {:?}, signer_id: {:?}, payload: {}, summary: {})",
            self.block_num,
            self.block_id,
            self.previous_id,
            self.signer_id,
            hex::encode(&self.payload),
            hex::encode(&self.summary),
        )
    }
}

pub type PeerId = Vec<u8>;

/// Information about a peer that is relevant to consensus
#[derive(Default, Debug)]
pub struct PeerInfo {
    pub peer_id: PeerId,
}

/// A consensus-related message sent between peers
#[derive(Default, Debug, Clone)]
pub struct PeerMessage {
    pub header: PeerMessageHeader,
    pub header_bytes: Vec<u8>,
    pub header_signature: Vec<u8>,
    pub content: Vec<u8>,
}

/// A header associated with a consensus-related message sent from a peer, can be used to verify
/// the origin of the message
#[derive(Default, Debug, Clone)]
pub struct PeerMessageHeader {
    /// The public key of the validator where this message originated
    ///
    /// NOTE: This may not be the validator that sent the message
    pub signer_id: Vec<u8>,
    pub content_sha512: Vec<u8>,
    pub message_type: String,
    pub name: String,
    pub version: String,
}

/// Engine is the only trait that needs to be implemented when adding a new consensus engine.
///
/// The consensus engine should listen for notifications from the validator about the status of
/// blocks and messages from peers. It must also determine internally when to build and publish
/// blocks based on its view of the network and the consensus algorithm it implements. Often this
/// will be some sort of timer-based interrupt.
///
/// Based on the updates the engine receives through the `Receiver<Update>` and the specifics of
/// the algorithm being implemented, the engine utilizes the provided `Service` to create new
/// blocks, communicate with its peers, request that certain blocks be committed, and fail or
/// ignore blocks that should not be committed.
///
/// While the validator may take actions beyond what the engine instructs it to do for performance
/// optimization reasons, it is the consensus engine's responsibility to drive the progress of the
/// validator and ensure liveness.
///
/// It is not the engine's responsibility to manage blocks or memory, other than to ensure it
/// responds to every new block with a commit, fail, or ignore within a "reasonable amount of
/// time". The validator is responsible for guaranteeing the integrity of all blocks sent to the
/// engine until the engine responds. After the engine responds, the validator does not guarantee
/// that the block and its predecessors continue to be available unless the block was committed.
///
/// Finally, as an optimization, the consensus engine can send prioritized lists of blocks to the
/// chain controller for checking instead of sending them one at a time, which allows the chain
/// controller to intelligently work ahead while the consensus engine makes its decisions.
pub trait Engine {
    /// Called after the engine is initialized, when a connection to the validator has been
    /// established. Notifications from the validator are sent along `updates`. `service` is used
    /// to send requests to the validator.
    fn start(
        &mut self,
        updates: Receiver<Update>,
        service: Box<Service>,
        startup_state: StartupState,
    ) -> Result<(), Error>;

    /// Get the version of this engine
    fn version(&self) -> String;

    /// Get the name of the engine, typically the algorithm being implemented
    fn name(&self) -> String;
}

/// State provided to an engine when it is started
#[derive(Debug, Default)]
pub struct StartupState {
    pub chain_head: Block,
    pub peers: Vec<PeerInfo>,
    pub local_peer_info: PeerInfo,
}

#[derive(Debug)]
pub enum Error {
    EncodingError(String),
    SendError(String),
    ReceiveError(String),
    InvalidState(String),
    UnknownBlock(String),
    UnknownPeer(String),
    NoChainHead,
    BlockNotReady,
}

impl error::Error for Error {
    fn description(&self) -> &str {
        use self::Error::*;
        match *self {
            EncodingError(ref s) => s,
            SendError(ref s) => s,
            ReceiveError(ref s) => s,
            InvalidState(ref s) => s,
            UnknownBlock(ref s) => s,
            UnknownPeer(ref s) => s,
            NoChainHead => "No chain head",
            BlockNotReady => "Block not ready to finalize",
        }
    }

    fn cause(&self) -> Option<&error::Error> {
        use self::Error::*;
        match *self {
            EncodingError(_) => None,
            SendError(_) => None,
            ReceiveError(_) => None,
            InvalidState(_) => None,
            UnknownBlock(_) => None,
            UnknownPeer(_) => None,
            NoChainHead => None,
            BlockNotReady => None,
        }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        use self::Error::*;
        match *self {
            EncodingError(ref s) => write!(f, "EncodingError: {}", s),
            SendError(ref s) => write!(f, "SendError: {}", s),
            ReceiveError(ref s) => write!(f, "ReceiveError: {}", s),
            InvalidState(ref s) => write!(f, "InvalidState: {}", s),
            UnknownBlock(ref s) => write!(f, "UnknownBlock: {}", s),
            UnknownPeer(ref s) => write!(f, "UnknownPeer: {}", s),
            NoChainHead => write!(f, "NoChainHead"),
            BlockNotReady => write!(f, "BlockNotReady"),
        }
    }
}

#[cfg(test)]
pub mod tests {
    use super::*;

    use std::default::Default;
    use std::sync::mpsc::{channel, RecvTimeoutError};
    use std::sync::{Arc, Mutex};
    use std::thread;
    use std::time::Duration;

    use consensus::service::tests::MockService;

    pub struct MockEngine {
        calls: Arc<Mutex<Vec<String>>>,
    }

    impl MockEngine {
        pub fn new() -> Self {
            MockEngine {
                calls: Arc::new(Mutex::new(Vec::new())),
            }
        }

        pub fn with(amv: Arc<Mutex<Vec<String>>>) -> Self {
            MockEngine { calls: amv }
        }

        pub fn calls(&self) -> Vec<String> {
            let calls = self.calls.lock().unwrap();
            let mut v = Vec::with_capacity((*calls).len());
            v.clone_from(&*calls);
            v
        }
    }

    impl Engine for MockEngine {
        fn start(
            &mut self,
            updates: Receiver<Update>,
            _service: Box<Service>,
            _startup_state: StartupState,
        ) -> Result<(), Error> {
            (*self.calls.lock().unwrap()).push("start".into());
            loop {
                match updates.recv_timeout(Duration::from_millis(100)) {
                    Ok(update) => {
                        // We don't check for exit() here because we want to drain all the updates
                        // before we exit. In a real implementation, exit() should also be checked
                        // here since there is no guarantee the queue will ever be empty.
                        match update {
                            Update::PeerConnected(_) => {
                                (*self.calls.lock().unwrap()).push("PeerConnected".into())
                            }
                            Update::PeerDisconnected(_) => {
                                (*self.calls.lock().unwrap()).push("PeerDisconnected".into())
                            }
                            Update::PeerMessage(_, _) => {
                                (*self.calls.lock().unwrap()).push("PeerMessage".into())
                            }
                            Update::BlockNew(_) => {
                                (*self.calls.lock().unwrap()).push("BlockNew".into())
                            }
                            Update::BlockValid(_) => {
                                (*self.calls.lock().unwrap()).push("BlockValid".into())
                            }
                            Update::BlockInvalid(_) => {
                                (*self.calls.lock().unwrap()).push("BlockInvalid".into())
                            }
                            Update::BlockCommit(_) => {
                                (*self.calls.lock().unwrap()).push("BlockCommit".into())
                            }
                            Update::Shutdown => {
                                println!("shutdown");
                                break;
                            }
                        };
                    }
                    Err(RecvTimeoutError::Disconnected) => {
                        println!("disconnected");
                        break;
                    }
                    Err(RecvTimeoutError::Timeout) => {
                        println!("timeout");
                    }
                }
            }

            Ok(())
        }
        fn version(&self) -> String {
            "0".into()
        }
        fn name(&self) -> String {
            "mock".into()
        }
    }

    #[test]
    fn test_engine() {
        // Create the mock engine with this vec so we can refer to it later. Once we put the engine
        // in a box, it is hard to get the vec back out.
        let calls = Arc::new(Mutex::new(Vec::new()));

        // We are going to run two threads to simulate the validator and the driver
        let mut mock_engine = MockEngine::with(calls.clone());

        let (sender, receiver) = channel();
        sender
            .send(Update::PeerConnected(Default::default()))
            .unwrap();
        sender
            .send(Update::PeerDisconnected(Default::default()))
            .unwrap();
        sender
            .send(Update::PeerMessage(Default::default(), Default::default()))
            .unwrap();
        sender.send(Update::BlockNew(Default::default())).unwrap();
        sender.send(Update::BlockValid(Default::default())).unwrap();
        sender
            .send(Update::BlockInvalid(Default::default()))
            .unwrap();
        sender
            .send(Update::BlockCommit(Default::default()))
            .unwrap();
        let handle = thread::spawn(move || {
            let svc = Box::new(MockService {});
            mock_engine
                .start(receiver, svc, Default::default())
                .unwrap();
        });
        sender.send(Update::Shutdown).unwrap();
        handle.join().unwrap();
        assert!(contains(&calls, "start"));
        assert!(contains(&calls, "PeerConnected"));
        assert!(contains(&calls, "PeerDisconnected"));
        assert!(contains(&calls, "PeerMessage"));
        assert!(contains(&calls, "BlockNew"));
        assert!(contains(&calls, "BlockValid"));
        assert!(contains(&calls, "BlockInvalid"));
        assert!(contains(&calls, "BlockCommit"));
    }

    fn contains(calls: &Arc<Mutex<Vec<String>>>, expected: &str) -> bool {
        for call in &*(calls.lock().unwrap()) {
            if expected == call {
                return true;
            }
        }
        false
    }
}

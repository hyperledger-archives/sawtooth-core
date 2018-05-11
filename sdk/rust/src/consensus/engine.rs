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

use std::ops::Deref;
use std::sync::{Mutex, atomic::{AtomicBool, Ordering}, mpsc::Receiver};

use consensus::service::Service;

/// An update from the validator
#[derive(Debug)]
pub enum Update {
    PeerConnected(PeerInfo),
    PeerDisconnected(PeerId),
    PeerMessage(PeerMessage),
    BlockNew(Block),
    BlockValid(BlockId),
    BlockInvalid(BlockId),
    BlockCommit(BlockId),
}

#[derive(Default, Debug)]
pub struct BlockId(Vec<u8>);
impl Deref for BlockId {
    type Target = Vec<u8>;

    fn deref(&self) -> &Vec<u8> {
        &self.0
    }
}
impl From<BlockId> for Vec<u8> {
    fn from(id: BlockId) -> Vec<u8> {
        id.0
    }
}
impl From<Vec<u8>> for BlockId {
    fn from(v: Vec<u8>) -> BlockId {
        BlockId(v)
    }
}

/// All information about a block that is relevant to consensus
#[derive(Default, Debug)]
pub struct Block {
    pub block_id: BlockId,
    pub previous_id: BlockId,
    pub signer_id: PeerId,
    pub block_num: u64,
    pub payload: Vec<u8>,
}

#[derive(Default, Debug)]
pub struct PeerId(Vec<u8>);
impl Deref for PeerId {
    type Target = Vec<u8>;

    fn deref(&self) -> &Vec<u8> {
        &self.0
    }
}
impl From<PeerId> for Vec<u8> {
    fn from(id: PeerId) -> Vec<u8> {
        id.0
    }
}
impl From<Vec<u8>> for PeerId {
    fn from(v: Vec<u8>) -> PeerId {
        PeerId(v)
    }
}

/// Information about a peer that is relevant to consensus
#[derive(Default, Debug)]
pub struct PeerInfo {
    pub peer_id: PeerId,
}

/// A consensus-related message sent between peers
#[derive(Default, Debug)]
pub struct PeerMessage {
    pub message_type: String,
    pub content: Vec<u8>,
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
pub trait Engine: Sync + Send {
    /// Called after the engine is initialized, when a connection to the validator has been
    /// established. Notifications from the validator are sent along `updates`. `service` is used
    /// to send requests to the validator.
    fn start(&self, updates: Receiver<Update>, service: Box<Service>);

    /// Called before the engine is dropped, to give the engine a chance to notify peers and
    /// cleanup
    fn stop(&self);

    /// Get the version of this engine
    fn version(&self) -> String;

    /// Get the name of the engine, typically the algorithm being implemented
    fn name(&self) -> String;
}

/// Utility class for signaling that a background thread should shutdown
#[derive(Default)]
pub struct Exit {
    flag: Mutex<AtomicBool>,
}

impl Exit {
    pub fn new() -> Self {
        Exit {
            flag: Mutex::new(AtomicBool::new(false)),
        }
    }

    pub fn get(&self) -> bool {
        self.flag.lock().unwrap().load(Ordering::Relaxed)
    }

    pub fn set(&self) {
        self.flag.lock().unwrap().store(true, Ordering::Relaxed);
    }
}

#[derive(Debug)]
pub enum Error {
    EncodingError(String),
    SendError(String),
    ReceiveError(String),
    InvalidState(String),
    UnknownBlock(String),
    UnknownPeer(String),
}

impl ::std::error::Error for Error {
    fn description(&self) -> &str {
        use self::Error::*;
        match *self {
            EncodingError(ref s) => s,
            SendError(ref s) => s,
            ReceiveError(ref s) => s,
            InvalidState(ref s) => s,
            UnknownBlock(ref s) => s,
            UnknownPeer(ref s) => s,
        }
    }

    fn cause(&self) -> Option<&::std::error::Error> {
        use self::Error::*;
        match *self {
            EncodingError(_) => None,
            SendError(_) => None,
            ReceiveError(_) => None,
            InvalidState(_) => None,
            UnknownBlock(_) => None,
            UnknownPeer(_) => None,
        }
    }
}

impl ::std::fmt::Display for Error {
    fn fmt(&self, f: &mut ::std::fmt::Formatter) -> ::std::fmt::Result {
        use self::Error::*;
        match *self {
            EncodingError(ref s) => write!(f, "EncodingError: {}", s),
            SendError(ref s) => write!(f, "SendError: {}", s),
            ReceiveError(ref s) => write!(f, "ReceiveError: {}", s),
            InvalidState(ref s) => write!(f, "InvalidState: {}", s),
            UnknownBlock(ref s) => write!(f, "UnknownBlock: {}", s),
            UnknownPeer(ref s) => write!(f, "UnknownPeer: {}", s),
        }
    }
}

#[cfg(test)]
pub mod tests {
    use super::*;

    use std::default::Default;
    use std::sync::mpsc::{channel, RecvTimeoutError};
    use std::sync::{Arc, Mutex};

    use consensus::service::tests::MockService;

    pub struct MockEngine {
        calls: Arc<Mutex<Vec<String>>>,
        exit: Exit,
    }

    impl MockEngine {
        pub fn new() -> Self {
            MockEngine {
                calls: Arc::new(Mutex::new(Vec::new())),
                exit: Exit::new(),
            }
        }

        pub fn with(amv: Arc<Mutex<Vec<String>>>) -> Self {
            MockEngine {
                calls: amv,
                exit: Exit::new(),
            }
        }

        pub fn calls(&self) -> Vec<String> {
            let calls = self.calls.lock().unwrap();
            let mut v = Vec::with_capacity((*calls).len());
            v.clone_from(&*calls);
            v
        }
    }

    impl Engine for MockEngine {
        fn start(&self, updates: Receiver<Update>, _service: Box<Service>) {
            (*self.calls.lock().unwrap()).push("start".into());
            loop {
                match updates.recv_timeout(::std::time::Duration::from_millis(100)) {
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
                            Update::PeerMessage(_) => {
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
                        };
                    }
                    Err(RecvTimeoutError::Disconnected) => {
                        println!("disconnected");
                        break;
                    }
                    Err(RecvTimeoutError::Timeout) => {
                        println!("timeout");
                        if self.exit.get() {
                            break;
                        }
                    }
                }
            }
        }
        fn stop(&self) {
            (*self.calls.lock().unwrap()).push("stop".into());
            self.exit.set();
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
        let eng = Arc::new(MockEngine::new());
        let eng_clone = eng.clone();
        let (sender, receiver) = channel();
        sender
            .send(Update::PeerConnected(Default::default()))
            .unwrap();
        sender
            .send(Update::PeerDisconnected(Default::default()))
            .unwrap();
        sender
            .send(Update::PeerMessage(Default::default()))
            .unwrap();
        sender.send(Update::BlockNew(Default::default())).unwrap();
        sender.send(Update::BlockValid(Default::default())).unwrap();
        sender
            .send(Update::BlockInvalid(Default::default()))
            .unwrap();
        sender
            .send(Update::BlockCommit(Default::default()))
            .unwrap();
        let handle = ::std::thread::spawn(move || {
            let svc = Box::new(MockService {});
            eng_clone.start(receiver, svc);
        });
        eng.stop();
        handle.join().unwrap();
        assert!(contains(&eng, "start"));
        assert!(contains(&eng, "PeerConnected"));
        assert!(contains(&eng, "PeerDisconnected"));
        assert!(contains(&eng, "PeerMessage"));
        assert!(contains(&eng, "BlockNew"));
        assert!(contains(&eng, "BlockValid"));
        assert!(contains(&eng, "BlockInvalid"));
        assert!(contains(&eng, "BlockCommit"));
        assert!(contains(&eng, "stop"));
    }

    fn contains(eng: &Arc<MockEngine>, expected: &str) -> bool {
        for call in eng.calls() {
            if expected == call {
                return true;
            }
        }
        false
    }
}

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

use std::sync::{Mutex, atomic::{AtomicBool, Ordering}};

use consensus::service::Service;

/// Consensus-related information about the block
#[derive(Default)]
pub struct Block {
    pub block_id: String,
    pub previous_id: String,
    pub signer_id: String,
    pub block_num: u64,
    pub consensus: Vec<u8>,
}

pub enum PeerUpdate {
    Connected(PeerInfo),
    Disconnected(String),
}

pub struct PeerInfo {
    pub peer_id: String,
}

/// Input is passed to a consensus engine through these methods
pub trait Engine: Sync + Send {
    /// Called when a new consensus message is received
    fn message(&self, message_type: String, message: Vec<u8>);

    /// Called when a new block is received
    fn block(&self, block: Block);

    /// Called when a peer's status changes
    fn peer(&self, peer: PeerUpdate);

    /// Called after the engine is initialized, when a connection to the validator has been
    /// established
    fn start(&self, service: Box<Service>);

    /// Called before the engine is dropped, to give the engine a chance to notify peers and
    /// cleanup
    fn stop(&self);

    /// Get the version of this engine
    fn version(&self) -> String;

    /// Get the name of the engine, typically the algorith being implemented
    fn name(&self) -> String;
}

/// Utility class for signaling that a background thread should shutdown
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
    DecodeError(String),
    EncodeError(String),
    SendError(String),
    ReceiveError(String),
    MissingResource(String),
    InvalidState(String),
}

impl ::std::error::Error for Error {
    fn description(&self) -> &str {
        use self::Error::*;
        match *self {
            DecodeError(ref s) => s,
            EncodeError(ref s) => s,
            SendError(ref s) => s,
            ReceiveError(ref s) => s,
            MissingResource(ref s) => s,
            InvalidState(ref s) => s,
        }
    }

    fn cause(&self) -> Option<&::std::error::Error> {
        use self::Error::*;
        match *self {
            DecodeError(_) => None,
            EncodeError(_) => None,
            SendError(_) => None,
            ReceiveError(_) => None,
            MissingResource(_) => None,
            InvalidState(_) => None,
        }
    }
}

impl ::std::fmt::Display for Error {
    fn fmt(&self, f: &mut ::std::fmt::Formatter) -> ::std::fmt::Result {
        use self::Error::*;
        match *self {
            DecodeError(ref s) => write!(f, "DecodeError: {}", s),
            EncodeError(ref s) => write!(f, "EncodeError: {}", s),
            SendError(ref s) => write!(f, "SendError: {}", s),
            ReceiveError(ref s) => write!(f, "ReceiveError: {}", s),
            MissingResource(ref s) => write!(f, "MissingResource: {}", s),
            InvalidState(ref s) => write!(f, "InvalidState: {}", s),
        }
    }
}

#[cfg(test)]
pub mod tests {
    use super::*;
    use std::default::Default;

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
        fn message(&self, _message_type: String, _payload: Vec<u8>) {
            println!("message()");
            (*self.calls.lock().unwrap()).push("message".into());
        }
        fn block(&self, _block: Block) {
            println!("block()");
            (*self.calls.lock().unwrap()).push("block".into());
        }
        fn peer(&self, _peer: PeerUpdate) {
            println!("peer()");
            (*self.calls.lock().unwrap()).push("peer".into());
        }
        fn start(&self, _service: Box<Service>) {
            println!("start()");
            (*self.calls.lock().unwrap()).push("start".into());
            while !self.exit.get() {
                ::std::thread::sleep(::std::time::Duration::from_millis(100));
            }
        }
        fn stop(&self) {
            println!("stop()");
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
        let handle = ::std::thread::spawn(move || {
            let svc = Box::new(MockService {});
            eng_clone.start(svc);
        });
        eng.block(Default::default());
        eng.peer(PeerUpdate::Disconnected(Default::default()));
        eng.message(Default::default(), Default::default());
        eng.stop();
        handle.join().unwrap();
        assert!(contains(&eng, "start"));
        assert!(contains(&eng, "block"));
        assert!(contains(&eng, "peer"));
        assert!(contains(&eng, "message"));
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

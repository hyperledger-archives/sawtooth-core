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

use consensus::engine::{Block, Error};

/// Provides methods that allow the consensus engine to issue commands and requests.
pub trait Service {
    /// Send a consensus message to a specific, connected peer
    fn send_to(&mut self, peer: &str, message_type: &str, payload: Vec<u8>) -> Result<(), Error>;

    /// Broadcast a message to all connected peers
    fn broadcast(&mut self, message_type: &str, payload: Vec<u8>) -> Result<(), Error>;

    /// Initialize a new block built on the block with the given previous id and
    /// begin adding batches to it. If no previous id is specified, the current
    /// head will be used.
    fn initialize_block(&mut self, previous_id: Option<String>) -> Result<(), Error>;

    /// Stop adding batches to the current block and finalize it. Include
    /// the given consensus data in the block. If this call is successful,
    /// the consensus engine will receive it afterwards.
    fn finalize_block(&mut self, data: Vec<u8>) -> Result<String, Error>;

    /// Stop adding batches to the current block and abandon it.
    fn cancel_block(&mut self) -> Result<(), Error>;

    /// Set the chain head to the given block id.
    fn commit_block(&mut self, block_id: String) -> Result<(), Error>;

    /// Request that this block not be cleaned up due to inactivity
    fn hold_block(&mut self, _block_id: String) -> Result<(), Error> {
        Ok(())
    }

    /// Retract a previous hold on a block
    fn drop_block(&mut self, _block_id: String) -> Result<(), Error> {
        Ok(())
    }

    /// Mark this block as invalid from the perspective of consensus
    fn fail_block(&mut self, _block_id: String) -> Result<(), Error> {
        Ok(())
    }

    /// Retrieve consensus-related information about a block
    fn get_block(&mut self, block_id: String) -> Result<Block, Error>;

    /// Read the value of the setting as of the given block
    fn get_setting(&mut self, block_id: String, setting: String) -> Result<Vec<u8>, Error>;

    /// Read the value of state at some address as of the given block
    fn get_state(&mut self, block_id: String, address: String) -> Result<Vec<u8>, Error>;
}

#[cfg(test)]
pub mod tests {
    use super::*;
    use std::default::Default;

    pub struct MockService {}

    impl Service for MockService {
        fn send_to(
            &mut self,
            _peer: &str,
            _message_type: &str,
            _payload: Vec<u8>,
        ) -> Result<(), Error> {
            Ok(())
        }
        fn broadcast(&mut self, _message_type: &str, _payload: Vec<u8>) -> Result<(), Error> {
            Ok(())
        }
        fn initialize_block(&mut self, _previous_id: Option<String>) -> Result<(), Error> {
            Ok(())
        }
        fn finalize_block(&mut self, _data: Vec<u8>) -> Result<String, Error> {
            Ok("".into())
        }
        fn cancel_block(&mut self) -> Result<(), Error> {
            Ok(())
        }
        fn commit_block(&mut self, _block_id: String) -> Result<(), Error> {
            Ok(())
        }
        fn hold_block(&mut self, _block_id: String) -> Result<(), Error> {
            Ok(())
        }
        fn drop_block(&mut self, _block_id: String) -> Result<(), Error> {
            Ok(())
        }
        fn fail_block(&mut self, _block_id: String) -> Result<(), Error> {
            Ok(())
        }
        fn get_block(&mut self, _block_id: String) -> Result<Block, Error> {
            Ok(Default::default())
        }
        fn get_setting(&mut self, _block_id: String, _setting: String) -> Result<Vec<u8>, Error> {
            Ok(Default::default())
        }
        fn get_state(&mut self, _block_id: String, _address: String) -> Result<Vec<u8>, Error> {
            Ok(Default::default())
        }
    }

    fn test_service<S: Service>(svc: &mut S) {
        svc.send_to("", Default::default(), Default::default())
            .unwrap();
        svc.broadcast(Default::default(), Default::default())
            .unwrap();
        svc.initialize_block(Default::default()).unwrap();
        svc.finalize_block(Default::default()).unwrap();
        svc.cancel_block().unwrap();
        svc.commit_block(Default::default()).unwrap();
        svc.get_block(Default::default()).unwrap();
        svc.get_setting(Default::default(), Default::default())
            .unwrap();
        svc.get_state(Default::default(), Default::default())
            .unwrap();
    }

    #[test]
    fn test_service_trait() {
        let mut ctx = MockService {};
        test_service(&mut ctx);
    }
}

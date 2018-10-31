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

use std::str::FromStr;
use std::sync::mpsc::{Receiver, RecvTimeoutError};
use std::thread::sleep;
use std::time;

use rand;
use rand::Rng;

use sawtooth_sdk::consensus::{engine::*, service::Service};

const DEFAULT_WAIT_TIME: u64 = 0;

#[derive(Default)]
struct LogGuard {
    not_ready_to_summarize: bool,
    not_ready_to_finalize: bool,
}

pub struct DevmodeService {
    service: Box<Service>,
    log_guard: LogGuard,
}

impl DevmodeService {
    pub fn new(service: Box<Service>) -> Self {
        DevmodeService {
            service,
            log_guard: LogGuard::default(),
        }
    }

    fn get_chain_head(&mut self) -> Block {
        debug!("Getting chain head");
        self.service
            .get_chain_head()
            .expect("Failed to get chain head")
    }

    fn get_block(&mut self, block_id: &BlockId) -> Block {
        debug!("Getting block {:?}", &block_id);
        self.service
            .get_blocks(vec![block_id.clone()])
            .expect("Failed to get block")
            .remove(block_id)
            .unwrap()
    }

    fn initialize_block(&mut self) {
        debug!("Initializing block");
        self.service
            .initialize_block(None)
            .expect("Failed to initialize");
    }

    fn finalize_block(&mut self) -> BlockId {
        debug!("Finalizing block");
        let mut summary = self.service.summarize_block();
        while let Err(Error::BlockNotReady) = summary {
            if !self.log_guard.not_ready_to_summarize {
                self.log_guard.not_ready_to_summarize = true;
                warn!("Block not ready to summarize");
            }
            sleep(time::Duration::from_secs(1));
            summary = self.service.summarize_block();
        }
        self.log_guard.not_ready_to_summarize = false;

        let consensus: Vec<u8> = create_consensus(&summary.expect("Failed to summarize block"));
        let mut block_id = self.service.finalize_block(consensus.clone());
        while let Err(Error::BlockNotReady) = block_id {
            if !self.log_guard.not_ready_to_finalize {
                self.log_guard.not_ready_to_finalize = true;
                warn!("Block not ready to finalize");
            }
            sleep(time::Duration::from_secs(1));
            block_id = self.service.finalize_block(consensus.clone());
        }
        self.log_guard.not_ready_to_finalize = false;

        block_id.expect("Failed to finalize block")
    }

    fn check_block(&mut self, block_id: BlockId) {
        debug!("Checking block {:?}", block_id);
        self.service
            .check_blocks(vec![block_id])
            .expect("Failed to check block");
    }

    fn fail_block(&mut self, block_id: BlockId) {
        debug!("Failing block {:?}", block_id);
        self.service
            .fail_block(block_id)
            .expect("Failed to fail block");
    }

    fn ignore_block(&mut self, block_id: BlockId) {
        debug!("Ignoring block {:?}", block_id);
        self.service
            .ignore_block(block_id)
            .expect("Failed to ignore block")
    }

    fn commit_block(&mut self, block_id: BlockId) {
        debug!("Committing block {:?}", block_id);
        self.service
            .commit_block(block_id)
            .expect("Failed to commit block");
    }

    fn cancel_block(&mut self) {
        debug!("Canceling block");
        match self.service.cancel_block() {
            Ok(_) => {}
            Err(Error::InvalidState(_)) => {}
            Err(err) => {
                panic!("Failed to cancel block: {:?}", err);
            }
        };
    }

    fn broadcast_published_block(&mut self, block_id: BlockId) {
        debug!("Broadcasting published block: {:?}", block_id);
        self.service
            .broadcast("published", Vec::from(block_id))
            .expect("Failed to broadcast published block");
    }

    fn send_block_received(&mut self, block: &Block) {
        let block = block.clone();

        self.service
            .send_to(&block.signer_id, "received", Vec::from(block.block_id))
            .expect("Failed to send block received");
    }

    fn send_block_ack(&mut self, sender_id: &PeerId, block_id: BlockId) {
        self.service
            .send_to(&sender_id, "ack", Vec::from(block_id))
            .expect("Failed to send block ack");
    }

    // Calculate the time to wait between publishing blocks. This will be a
    // random number between the settings sawtooth.consensus.min_wait_time and
    // sawtooth.consensus.max_wait_time if max > min, else DEFAULT_WAIT_TIME. If
    // there is an error parsing those settings, the time will be
    // DEFAULT_WAIT_TIME.
    fn calculate_wait_time(&mut self, chain_head_id: BlockId) -> time::Duration {
        let settings_result = self.service.get_settings(
            chain_head_id,
            vec![
                String::from("sawtooth.consensus.min_wait_time"),
                String::from("sawtooth.consensus.max_wait_time"),
            ],
        );

        let wait_time = if let Ok(settings) = settings_result {
            let ints: Vec<u64> = vec![
                &settings["sawtooth.consensus.min_wait_time"],
                &settings["sawtooth.consensus.max_wait_time"],
            ].iter()
            .map(|string| string.parse::<u64>())
            .map(|result| result.unwrap_or(0))
            .collect();

            let min_wait_time: u64 = ints[0];
            let max_wait_time: u64 = ints[1];

            debug!("Min: {:?} -- Max: {:?}", min_wait_time, max_wait_time);

            if min_wait_time >= max_wait_time {
                DEFAULT_WAIT_TIME
            } else {
                rand::thread_rng().gen_range(min_wait_time, max_wait_time)
            }
        } else {
            DEFAULT_WAIT_TIME
        };

        info!("Wait time: {:?}", wait_time);

        time::Duration::from_secs(wait_time)
    }
}

pub struct DevmodeEngine {}

impl DevmodeEngine {
    pub fn new() -> Self {
        DevmodeEngine {}
    }
}

impl Engine for DevmodeEngine {
    fn start(
        &mut self,
        updates: Receiver<Update>,
        service: Box<Service>,
        startup_state: StartupState,
    ) -> Result<(), Error> {
        let mut service = DevmodeService::new(service);
        let mut chain_head = startup_state.chain_head;

        let mut wait_time = service.calculate_wait_time(chain_head.block_id.clone());
        let mut published_at_height = false;
        let mut start = time::Instant::now();

        service.initialize_block();

        // 1. Wait for an incoming message.
        // 2. Check for exit.
        // 3. Handle the message.
        // 4. Check for publishing.
        loop {
            let incoming_message = updates.recv_timeout(time::Duration::from_millis(10));

            match incoming_message {
                Ok(update) => {
                    debug!("Received message: {:?}", update);

                    match update {
                        Update::Shutdown => {
                            break;
                        }
                        Update::BlockNew(block) => {
                            info!("Checking consensus data: {:?}", block);

                            if check_consensus(&block) {
                                info!("Passed consensus check: {:?}", block);
                                service.check_block(block.block_id);
                            } else {
                                info!("Failed consensus check: {:?}", block);
                                service.fail_block(block.block_id);
                            }
                        }

                        Update::BlockValid(block_id) => {
                            let block = service.get_block(&block_id);

                            service.send_block_received(&block);

                            chain_head = service.get_chain_head();

                            info!(
                                "Choosing between chain heads -- current: {:?} -- new: {:?}",
                                chain_head, block
                            );

                            // Advance the chain if possible.
                            if block.block_num > chain_head.block_num
                                || (block.block_num == chain_head.block_num
                                    && block.block_id > chain_head.block_id)
                            {
                                info!("Committing {:?}", block);
                                service.commit_block(block_id);
                            } else if block.block_num < chain_head.block_num {
                                let mut chain_block = chain_head;
                                loop {
                                    chain_block = service.get_block(&chain_block.previous_id);
                                    if chain_block.block_num == block.block_num {
                                        break;
                                    }
                                }
                                if block.block_id > chain_block.block_id {
                                    info!("Switching to new fork {:?}", block);
                                    service.commit_block(block_id);
                                } else {
                                    info!("Ignoring fork {:?}", block);
                                    service.ignore_block(block_id);
                                }
                            } else {
                                info!("Ignoring {:?}", block);
                                service.ignore_block(block_id);
                            }
                        }

                        // The chain head was updated, so abandon the
                        // block in progress and start a new one.
                        Update::BlockCommit(new_chain_head) => {
                            info!(
                                "Chain head updated to {:?}, abandoning block in progress",
                                new_chain_head
                            );

                            service.cancel_block();

                            wait_time = service.calculate_wait_time(new_chain_head.clone());
                            published_at_height = false;
                            start = time::Instant::now();

                            service.initialize_block();
                        }

                        Update::PeerMessage(message, sender_id) => {
                            match DevmodeMessage::from_str(message.header.message_type.as_ref()).unwrap() {
                                DevmodeMessage::Published => {
                                    let block_id = BlockId::from(message.content);
                                    info!(
                                        "Received block published message from {:?}: {:?}",
                                        &sender_id, block_id
                                    );
                                }

                                DevmodeMessage::Received => {
                                    let block_id = BlockId::from(message.content);
                                    info!(
                                        "Received block received message from {:?}: {:?}",
                                        &sender_id, block_id
                                    );
                                    service.send_block_ack(&sender_id, block_id);
                                }

                                DevmodeMessage::Ack => {
                                    let block_id = BlockId::from(message.content);
                                    info!(
                                        "Received ack message from {:?}: {:?}",
                                        &sender_id, block_id
                                    );
                                }
                            }
                        }

                        // Devmode doesn't care about peer notifications
                        // or invalid blocks.
                        _ => {}
                    }
                }

                Err(RecvTimeoutError::Disconnected) => {
                    error!("Disconnected from validator");
                    break;
                }

                Err(RecvTimeoutError::Timeout) => {}
            }

            if !published_at_height && time::Instant::now().duration_since(start) > wait_time {
                info!("Timer expired -- publishing block");
                let new_block_id = service.finalize_block();
                published_at_height = true;

                service.broadcast_published_block(new_block_id);
            }
        }

        Ok(())
    }

    fn version(&self) -> String {
        "0.1".into()
    }

    fn name(&self) -> String {
        "Devmode".into()
    }
}

fn check_consensus(block: &Block) -> bool {
    block.payload == create_consensus(&block.summary)
}

fn create_consensus(summary: &[u8]) -> Vec<u8> {
    let mut consensus: Vec<u8> = Vec::from(&b"Devmode"[..]);
    consensus.extend_from_slice(summary);
    consensus
}

pub enum DevmodeMessage {
    Ack,
    Published,
    Received,
}

impl FromStr for DevmodeMessage {
    type Err = &'static str;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "ack" => Ok(DevmodeMessage::Ack),
            "published" => Ok(DevmodeMessage::Published),
            "received" => Ok(DevmodeMessage::Received),
            _ => Err("Invalid message type"),
        }
    }
}

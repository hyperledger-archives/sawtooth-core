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

use std::sync::mpsc::{Receiver, RecvTimeoutError};
use std::thread::sleep;
use std::time;

use rand;
use rand::Rng;

use sawtooth_sdk::consensus::{engine::*, service::Service};

const DEFAULT_WAIT_TIME: u64 = 0;

pub struct DevmodeService {
    service: Box<Service>,
}

impl DevmodeService {
    pub fn new(service: Box<Service>) -> Self {
        DevmodeService { service }
    }

    fn wait_for_chain_head(&mut self) -> Block {
        let mut query_result = self.service.get_chain_head();

        while let Err(Error::NoChainHead) = query_result {
            warn!("Waiting for chain head");
            sleep(time::Duration::from_millis(200));
            query_result = self.service.get_chain_head();
        }

        query_result.expect("Failed to get chain head")
    }

    fn get_chain_head(&mut self) -> Block {
        debug!("Getting chain head");
        self.service
            .get_chain_head()
            .expect("Failed to get chain head")
    }

    fn get_block(&mut self, block_id: BlockId) -> Block {
        debug!("Getting block {:?}", block_id);
        self.service
            .get_blocks(vec![block_id.clone()])
            .expect("Failed to get block")
            .remove(&block_id)
            .unwrap()
    }

    fn initialize_block(&mut self) {
        debug!("Initializing block");
        self.service
            .initialize_block(None)
            .expect("Failed to initialize");
    }

    fn finalize_block(&mut self) {
        debug!("Finalizing block");
        let mut query_result = self.service.finalize_block(Vec::from(&b"Devmode"[..]));

        while let Err(Error::BlockNotReady) = query_result {
            warn!("Block not ready");
            sleep(time::Duration::from_secs(1));
            query_result = self.service.finalize_block(Vec::from(&b"Devmode"[..]));
        }

        query_result.expect("Failed to finalize block");
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
                settings.get("sawtooth.consensus.min_wait_time").unwrap(),
                settings.get("sawtooth.consensus.max_wait_time").unwrap(),
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

pub struct DevmodeEngine {
    exit: Exit,
}

impl DevmodeEngine {
    pub fn new() -> Self {
        DevmodeEngine { exit: Exit::new() }
    }
}

impl Engine for DevmodeEngine {
    fn start(&self, updates: Receiver<Update>, service: Box<Service>) {
        let mut service = DevmodeService::new(service);

        let mut chain_head = service.wait_for_chain_head();
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

            if self.exit.get() {
                break;
            }

            match incoming_message {
                Ok(update) => {
                    debug!("Received message: {:?}", update);

                    match update {
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
                            let block = service.get_block(block_id.clone());
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
                service.finalize_block();
                published_at_height = true;
            }
        }
    }

    fn stop(&self) {
        self.exit.set();
    }

    fn version(&self) -> String {
        "0.1".into()
    }

    fn name(&self) -> String {
        "Devmode".into()
    }
}

fn check_consensus(block: &Block) -> bool {
    block.payload == b"Devmode"
}

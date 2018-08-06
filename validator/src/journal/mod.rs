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

pub const NULL_BLOCK_IDENTIFIER: &str = "0000000000000000";

pub mod block_manager;
pub mod block_manager_ffi;
pub mod block_store;
pub mod block_validator;
pub mod block_wrapper;
pub mod block_wrapper_ffi;
mod candidate_block;
pub mod chain;
mod chain_commit_state;
pub mod chain_ffi;
pub mod chain_head_lock;
pub mod chain_head_lock_ffi;
mod chain_id_manager;
mod fork_cache;
pub mod incoming_batch_queue_ffi;
pub mod publisher;
pub mod publisher_ffi;
mod validation_rule_enforcer;

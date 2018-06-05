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

use cpython;

use scheduler::Scheduler;

/// The logical state hash before state has been added to the
/// merkle database. May not be the actual first state hash due to
/// implementation details of the merkle database.
pub const NULL_STATE_HASH: &str = "";

pub trait ExecutionPlatform: Sync + Send {
    fn create_scheduler(&self, state_hash: &str) -> Result<Box<Scheduler>, cpython::PyErr>;
}

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

use proto::events::Event;
use proto::transaction_receipt::StateChange;

mod execution_result_ffi;
use batch::Batch;

pub mod py_scheduler;

pub trait Scheduler: Sync + Send {
    /// Add a batch to the scheduler, optionally specifying that the transactions
    /// in this batch and each of the batches in order up to this one should produce a
    /// Merkle root specified by expected_state_hash. If the two roots are equal, the results of
    /// the block are written to the database, otherwise not.
    fn add_batch(
        &mut self,
        batch: Batch,
        expected_state_hash: Option<&str>,
        required: bool,
    ) -> Result<(), SchedulerError>;

    /// Signal to the scheduler that it can finish it's work and no
    /// more batches will be handed to it.
    fn finalize(&mut self, unschedule_incomplete: bool) -> Result<(), SchedulerError>;

    /// Cancel the scheduling of the supplied transactions as they are no longer needed.
    fn cancel(&mut self) -> Result<(), SchedulerError>;

    /// Ask if the ExecutionResults are ready, optionally blocking until they become available.
    fn complete(&mut self, block: bool) -> Result<Option<ExecutionResults>, SchedulerError>;
}

pub struct ExecutionResults {
    pub beginning_state_hash: Option<String>,
    pub ending_state_hash: Option<String>,
    pub batch_results: Vec<BatchExecutionResult>,
}

pub type BatchExecutionResult = (String, Option<Vec<TxnExecutionResult>>);

#[derive(Clone, Debug)]
pub struct TxnExecutionResult {
    pub signature: String,
    pub is_valid: bool,
    pub state_changes: Vec<StateChange>,
    pub events: Vec<Event>,
    pub data: Vec<Vec<u8>>,
    pub error_message: String,
    pub error_data: Vec<u8>,
}

#[derive(Debug)]
pub enum SchedulerError {
    /// The scheduler transition is not allowed by the Finite State Machine.
    FSMError(String),
    Other(String),
}

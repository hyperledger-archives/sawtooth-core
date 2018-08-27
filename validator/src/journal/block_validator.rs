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
use cpython::{FromPyObject, ObjectProtocol, PyObject, Python};

use block::Block;
use journal::{block_manager::BlockManager, block_store::BlockStore, block_wrapper::BlockStatus};
use scheduler::TxnExecutionResult;
use std::sync::mpsc::Sender;

#[derive(Clone, Debug, PartialEq)]
pub enum ValidationError {
    BlockValidationFailure(String),
    BlockValidationError(String),
    BlockStoreUpdated,
}

pub trait BlockValidator: Sync + Send + Clone {
    fn has_block(&self, block_id: &str) -> bool;

    fn validate_block(&self, block: Block) -> Result<(), ValidationError>;

    fn submit_blocks_for_verification(
        &self,
        blocks: &[Block],
        response_sender: Sender<BlockValidationResult>,
    );

    fn process_pending(&self, block: &Block, response_sender: Sender<BlockValidationResult>);
}

pub trait BlockStatusStore {
    fn status(&self, block_id: &str) -> BlockStatus;
}

#[derive(Clone, Debug)]
pub struct BlockValidationResult {
    pub block_id: String,
    pub execution_results: Vec<TxnExecutionResult>,
    pub num_transactions: u64,
    pub status: BlockStatus,
}

impl<'source> FromPyObject<'source> for BlockValidationResult {
    fn extract(py: Python, obj: &'source PyObject) -> cpython::PyResult<Self> {
        let status: BlockStatus = obj.getattr(py, "status")?.extract(py)?;
        let execution_results: Vec<TxnExecutionResult> =
            obj.getattr(py, "execution_results")?.extract(py)?;
        let block_id: String = obj.getattr(py, "block_id")?.extract(py)?;
        let num_transactions = obj.getattr(py, "num_transactions")?.extract(py)?;

        Ok(BlockValidationResult {
            block_id,
            execution_results,
            num_transactions,
            status,
        })
    }
}

/// A generic block validation. Returns a ValidationError::BlockValidationFailure on
/// validation failure. It is a dependent validation if it can return
/// ValidationError::BlockStoreUpdated and is an independent validation otherwise
trait BlockValidation {
    type ReturnValue;

    fn validate_block(
        &self,
        block: &Block,
        previous_state_root: Option<&String>,
    ) -> Result<Self::ReturnValue, ValidationError>;
}

/// A check that determines if the Dependent checks are honored. If this check
/// returns false, the dependent checks are honored.
trait BlockStoreUpdatedCheck {
    fn check_chain_head_updated(
        &self,
        expected_chain_head_id: Option<&String>,
    ) -> Result<bool, ValidationError>;
}

struct BlockValidationProcessor<
    BS: BlockStore,
    SBV: BlockValidation<ReturnValue = BlockValidationResult>,
    C: BlockStoreUpdatedCheck,
> {
    block_store: BS,
    block_manager: BlockManager,
    dependent_validations: Vec<Box<BlockValidation<ReturnValue = ()>>>,
    independent_validations: Vec<Box<BlockValidation<ReturnValue = ()>>>,
    state_validation: SBV,
    check: C,
}

impl<
        BS: BlockStore,
        SBV: BlockValidation<ReturnValue = BlockValidationResult>,
        C: BlockStoreUpdatedCheck,
    > BlockValidationProcessor<BS, SBV, C>
{
    fn new(
        block_store: BS,
        block_manager: BlockManager,
        dependent_validations: Vec<Box<BlockValidation<ReturnValue = ()>>>,
        independent_validations: Vec<Box<BlockValidation<ReturnValue = ()>>>,
        state_validation: SBV,
        check: C,
    ) -> Self {
        BlockValidationProcessor {
            block_store,
            block_manager,
            dependent_validations,
            independent_validations,
            state_validation,
            check,
        }
    }

    fn validate_block(&self, block: &Block) -> Result<BlockValidationResult, ValidationError> {
        let previous_blocks_state_hash = self
            .block_manager
            .get(&[&block.previous_block_id])
            .next()
            .unwrap_or(None)
            .map(|b| b.state_root_hash.clone());

        let checks = 'outer: loop {
            let chain_head_option = self
                .block_store
                .iter()
                .map_err(|err| {
                    ValidationError::BlockValidationError(format!(
                        "There was an error reading from the BlockStore: {:?}",
                        err
                    ))
                })?
                .next()
                .map(|b| b.header_signature.clone());
            let mut dependent_checks = vec![];
            for validation in &self.dependent_validations {
                match validation.validate_block(&block, previous_blocks_state_hash.as_ref()) {
                    Ok(()) => (),
                    Err(ValidationError::BlockStoreUpdated) => {
                        warn!(
                            "Blockstore updated during validation of block {}, retrying checks",
                            &block.header_signature
                        );
                        continue 'outer;
                    }
                    Err(err) => dependent_checks.push(Err(err)),
                }
            }

            if !self
                .check
                .check_chain_head_updated(chain_head_option.as_ref())?
            {
                break dependent_checks;
            }
        };
        for check in checks {
            check?;
        }

        for validation in &self.independent_validations {
            match validation.validate_block(&block, previous_blocks_state_hash.as_ref()) {
                Ok(()) => (),
                Err(err) => return Err(err),
            }
        }

        self.state_validation
            .validate_block(&block, previous_blocks_state_hash.as_ref())
    }
}

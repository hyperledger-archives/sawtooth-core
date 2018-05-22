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

use block::Block;
use proto::transaction_receipt::TransactionReceipt;

pub trait ChainObserver {
    /// This method is called by the ChainController on block boundaries.
    ///
    /// Args:
    ///     block: The block that was just committed.
    ///     receipts: transaction receipts for all transactions in the block.
    fn chain_update(&mut self, block: &Block, receipts: &[&TransactionReceipt]);
}

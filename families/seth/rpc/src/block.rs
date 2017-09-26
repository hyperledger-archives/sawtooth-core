/*
 * Copyright 2017 Intel Corporation
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

use jsonrpc_core::{Params, Value, Error};
use protobuf;

use error;

use super::requests::{ValidatorClient};

use sawtooth_sdk::messaging::stream::*;

use sawtooth_sdk::messages::client::{
    ClientBlockListRequest, ClientBlockListResponse, PagingControls,
};
use sawtooth_sdk::messages::block::BlockHeader;
use sawtooth_sdk::messages::validator::Message_MessageType;

// Return the block number of the current chain head, in hex, as a string
pub fn block_number<T>(_params: Params, mut client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    info!("eth_blockNumber");
    let mut paging = PagingControls::new();
    paging.set_count(1);
    let mut request = ClientBlockListRequest::new();
    request.set_paging(paging);

    let response: ClientBlockListResponse =
        match client.request(Message_MessageType::CLIENT_BLOCK_LIST_REQUEST, &request)
    {
        Ok(r) => r,
        Err(error) => {
            error!("{}", error);
            return Err(Error::internal_error());
        }
    };

    let block = &response.blocks[0];
    let block_header: BlockHeader = match protobuf::parse_from_bytes(&block.header) {
        Ok(r) => r,
        Err(error) => {
            error!("Error parsing block header: {:?}", error);
            return Err(Error::internal_error());
        }
    };

    Ok(Value::String(format!("{:#x}", block_header.block_num).into()))
}

pub fn get_block_by_hash<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}
pub fn get_block_by_number<T>(_params: Params, mut _client: ValidatorClient<T>) -> Result<Value, Error> where T: MessageSender {
    Err(error::not_implemented())
}

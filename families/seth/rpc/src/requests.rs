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

use futures_cpupool::{CpuPool};
use jsonrpc_core::{Params, Value, Error, BoxFuture};

use sawtooth_sdk::messaging::stream::*;
use sawtooth_sdk::messages::validator::Message_MessageType;

use protobuf;
use uuid;


pub type RequestHandler<T> = fn(Params, ValidatorClient<T>) -> Result<Value, Error>;

#[derive(Clone)]
pub struct RequestExecutor<T: MessageSender + Clone + Sync + Send + 'static> {
    pool: CpuPool,
    client: ValidatorClient<T>,
}

impl<T: MessageSender + Clone + Sync + Send + 'static> RequestExecutor<T> {
    pub fn new(sender: T) -> Self {
        RequestExecutor {
            pool: CpuPool::new_num_cpus(),
            client: ValidatorClient::new(sender),
        }
    }

    pub fn run(&self, params: Params, handler: RequestHandler<T>) -> BoxFuture<Value, Error> {
        let client = self.client.clone();
        Box::new(self.pool.spawn_fn(move || {handler(params, client)}))
    }

}

#[derive(Clone)]
pub struct ValidatorClient<S: MessageSender> {
    sender: S,
}

impl<S: MessageSender> ValidatorClient<S> {
    pub fn new(sender: S) -> Self {
        ValidatorClient{ sender: sender }
    }

    pub fn request<T, U>(&mut self, msg_type: Message_MessageType, msg: T) -> Result<U, String>
        where T: protobuf::Message, U: protobuf::MessageStatic
    {
        let msg_bytes = match protobuf::Message::write_to_bytes(&msg) {
            Ok(b) => b,
            Err(error) => {
                return Err(String::from(format!("Error serializing request: {:?}", error)));
            },
        };

        let correlation_id = match uuid::Uuid::new(uuid::UuidVersion::Random) {
            Some(cid) => cid.to_string(),
            None => {
                return Err(String::from("Error generating UUID"));
            },
        };

        let mut future = match self.sender.send(msg_type, &correlation_id, &msg_bytes) {
            Ok(f) => f,
            Err(error) => {
                return Err(String::from(format!("Error unwrapping future: {:?}", error)));
            },
        };

        let response_msg = match future.get() {
            Ok(m) => m,
            Err(error) => {
                return Err(String::from(format!("Error getting future: {:?}", error)));
            },
        };

        let response: U = match protobuf::parse_from_bytes(&response_msg.content) {
            Ok(r) => r,
            Err(error) => {
                return Err(String::from(format!("Error parsing response: {:?}", error)));
            },
        };

        Ok(response)
    }
}

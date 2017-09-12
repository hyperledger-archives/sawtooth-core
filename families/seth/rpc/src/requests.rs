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

use sawtooth_sdk::messaging::zmq_stream::*;

pub type RequestHandler = fn(params: Params, sender: ZmqMessageSender) -> Result<Value, Error>;

#[derive(Clone)]
pub struct RequestExecutor {
    pool: CpuPool,
    sender: ZmqMessageSender,
}

impl RequestExecutor {
    pub fn new(sender: ZmqMessageSender) -> Self {
        RequestExecutor {
            pool: CpuPool::new_num_cpus(),
            sender: sender,
        }
    }

    pub fn run(&self, params: Params, handler: RequestHandler) -> BoxFuture<Value, Error> {
        let sender = self.sender.clone();
        Box::new(self.pool.spawn_fn(move || {handler(params, sender)}))
    }

}

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

use super::client::{ValidatorClient};


pub type RequestHandler<T> = fn(Params, ValidatorClient<T>) -> Result<Value, Error>;

#[derive(Clone)]
pub struct RequestExecutor<T: MessageSender + Clone + Sync + Send + 'static> {
    pool: CpuPool,
    client: ValidatorClient<T>,
}

impl<T: MessageSender + Clone + Sync + Send + 'static> RequestExecutor<T> {
    pub fn new(client: ValidatorClient<T>) -> Self {
        RequestExecutor {
            pool: CpuPool::new_num_cpus(),
            client: client,
        }
    }

    pub fn run(&self, params: Params, handler: RequestHandler<T>) -> BoxFuture<Value, Error> {
        let client = self.client.clone();
        Box::new(self.pool.spawn_fn(move || {handler(params, client)}))
    }

}

// Copyright 2018 Intel Corporation
// Copyright 2020 Walmart Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

use std::collections::HashMap;

#[derive(Copy, Clone)]
pub enum Level {
    Info,
}

impl Default for Level {
    fn default() -> Self {
        Level::Info
    }
}

pub trait Counter: Send + Sync {
    fn inc(&mut self);
    fn inc_n(&mut self, value: usize);
    fn dec_n(&mut self, value: usize);
}

pub trait Gauge<T>: Send + Sync {
    fn set_value(&mut self, value: T);
}

pub trait MetricsCollectorHandle<S: AsRef<str>, T>: Send + Sync {
    fn counter(
        &self,
        metric_name: S,
        level: Option<Level>,
        tags: Option<HashMap<String, String>>,
    ) -> Box<dyn Counter>;

    fn gauge(
        &self,
        metric_name: S,
        level: Option<Level>,
        tags: Option<HashMap<String, String>>,
    ) -> Box<dyn Gauge<T>>;
}

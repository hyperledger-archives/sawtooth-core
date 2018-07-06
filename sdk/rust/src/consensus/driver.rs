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

use consensus::engine::{Engine, Error};

pub trait Driver {
    fn new(engine: Box<Engine>) -> Self;
    fn start(&self, endpoint: &str) -> Result<(), Error>;
    fn stop(&self);
}

#[cfg(test)]
pub mod tests {
    use super::*;

    use std::sync::mpsc::channel;

    use consensus::engine::tests::MockEngine;
    use consensus::service::tests::MockService;

    pub struct MockDriver {
        engine: Box<Engine>,
    }

    impl Driver for MockDriver {
        fn new(engine: Box<Engine>) -> Self {
            MockDriver { engine }
        }

        fn start(&self, _endpoint: &str) -> Result<(), Error> {
            let service = Box::new(MockService {});
            let (_sender, receiver) = channel();
            self.engine
                .start(receiver, service, Default::default());
            Ok(())
        }

        fn stop(&self) {}
    }

    #[test]
    fn test_harness() {
        // Just test that we can create a driver
        let engine = Box::new(MockEngine::new());
        MockDriver::new(engine);
    }
}

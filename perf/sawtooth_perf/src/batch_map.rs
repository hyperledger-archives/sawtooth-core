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

use std::collections::HashMap;

use sawtooth_sdk::messages::batch::BatchList;

pub struct BatchMap {
    // Batches that haven't been successfully submitted to
    // a validator.
    batches_by_id: HashMap<String, BatchList>,
}

impl BatchMap {
    pub fn new() -> BatchMap {
        BatchMap {
            batches_by_id: HashMap::new(),
        }
    }

    // Mark that batchlist associated with batch id has been submitted
    // to a validator.
    pub fn mark_submit_success(&mut self, batch_id: &str) {
        self.batches_by_id.remove(batch_id);
    }

    // Get a batchlist by id, to submit it to a validator.
    pub fn get_batchlist_to_submit(&mut self, batch_id: &str) -> Option<BatchList> {
        self.batches_by_id.get(batch_id).cloned()
    }

    // Idempotent method for adding a BatchList
    pub fn add(&mut self, batchlist: BatchList) {
        if let Some(batch_id) = batchlist.batches.last().map(|b| b.header_signature.clone()) {
            self.batches_by_id.entry(batch_id).or_insert(batchlist);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::BatchMap;

    use rand::Rng;
    use rand::StdRng;

    use protobuf::RepeatedField;

    use sawtooth_sdk::messages::batch::Batch;
    use sawtooth_sdk::messages::batch::BatchList;
    use sawtooth_sdk::signing;

    #[test]
    fn test_2_cycles_of_retries() {
        let mut timed_batch_iterator = BatchMap::new();
        let mut batchlists = generate_batchlists(3);

        let batchlist1 = batchlists.pop();
        let batchlist2 = batchlists.pop();
        let batchlist3 = batchlists.pop();

        let batch_id1 = batchlist1
            .clone()
            .unwrap()
            .batches
            .last()
            .unwrap()
            .header_signature
            .clone();
        let batch_id2 = batchlist2
            .clone()
            .unwrap()
            .batches
            .last()
            .unwrap()
            .header_signature
            .clone();
        let batch_id3 = batchlist3
            .clone()
            .unwrap()
            .batches
            .last()
            .unwrap()
            .header_signature
            .clone();

        timed_batch_iterator.add(batchlist1.clone().unwrap());
        timed_batch_iterator.add(batchlist2.clone().unwrap());
        timed_batch_iterator.add(batchlist3.clone().unwrap());

        timed_batch_iterator.add(batchlist1.clone().unwrap());
        timed_batch_iterator.add(batchlist2.clone().unwrap());
        timed_batch_iterator.add(batchlist3.clone().unwrap());

        timed_batch_iterator.mark_submit_success(&batch_id1);
        timed_batch_iterator.mark_submit_success(&batch_id3);

        assert_eq!(
            timed_batch_iterator.get_batchlist_to_submit(&batch_id2),
            batchlist2
        );
        assert_eq!(
            timed_batch_iterator.get_batchlist_to_submit(&batch_id1),
            None
        );
        assert_eq!(
            timed_batch_iterator.get_batchlist_to_submit(&batch_id3),
            None
        );

        timed_batch_iterator.mark_submit_success(&batch_id2);

        assert_eq!(
            timed_batch_iterator.get_batchlist_to_submit(&batch_id2),
            None
        );
    }

    fn generate_batchlists(num: u32) -> Vec<BatchList> {
        let context = signing::create_context("secp256k1").unwrap();
        let private_key = context.new_random_private_key().unwrap();
        let _signer = signing::Signer::new(context.as_ref(), private_key.as_ref());

        let mut batchlists = Vec::new();

        let mut rng = StdRng::new().unwrap();

        for _ in 0..num {
            let mut batch = Batch::new();
            let mut batchlist = BatchList::new();

            batch.set_header_signature(rng.gen_iter::<char>().take(100).collect());

            let batches = RepeatedField::from_vec(vec![batch]);

            batchlist.set_batches(batches);

            batchlists.push(batchlist);
        }
        batchlists
    }
}

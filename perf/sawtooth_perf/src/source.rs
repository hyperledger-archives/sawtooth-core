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

//! Tools for generating signed batches from a stream of transactions

extern crate protobuf;

use std::io::Read;
use std::marker::PhantomData;

use self::protobuf::Message;

/// Decodes Protocol Buffer messages from a length-delimited input reader.
pub struct LengthDelimitedMessageSource<'a, T: 'a> {
    source: protobuf::CodedInputStream<'a>,
    phantom: PhantomData<&'a T>,
}

impl<'a, T> LengthDelimitedMessageSource<'a, T>
where
    T: Message,
{
    /// Creates a new `LengthDelimitedMessageSource` from a given reader.
    pub fn new(source: &'a mut Read) -> Self {
        let source = protobuf::CodedInputStream::new(source);
        LengthDelimitedMessageSource {
            source,
            phantom: PhantomData,
        }
    }

    /// Returns the next set of messages.
    /// The vector of messages will contain up to `max_msgs` number of
    /// messages.  An empty vector indicates that the source has been consumed.
    pub fn next(&mut self, max_msgs: usize) -> Result<Vec<T>, protobuf::ProtobufError> {
        let mut results = Vec::with_capacity(max_msgs);
        for _ in 0..max_msgs {
            if self.source.eof()? {
                break;
            }

            // read the delimited length
            let next_len = try!(self.source.read_raw_varint32());
            let buf = try!(self.source.read_raw_bytes(next_len));

            let msg = try!(protobuf::parse_from_bytes(&buf));
            results.push(msg);
        }
        Ok(results)
    }
}

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

extern crate glob;
extern crate protoc_rust;

use protoc_rust::Customize;

fn main() {
    let proto_src_files = glob_simple("../protos/*.proto");
    println!("{:?}", proto_src_files);

    protoc_rust::run(protoc_rust::Args {
        out_dir: "./src",
        input: &proto_src_files
            .iter()
            .map(|a| a.as_ref())
            .collect::<Vec<&str>>(),
        includes: &["../protos"],
        customize: Customize::default(),
    }).expect("Error generating rust files from smallbank protos");
}

fn glob_simple(pattern: &str) -> Vec<String> {
    glob::glob(pattern)
        .expect("glob")
        .map(|g| {
            g.expect("item")
                .as_path()
                .to_str()
                .expect("utf-8")
                .to_owned()
        }).collect()
}

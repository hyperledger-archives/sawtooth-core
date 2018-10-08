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

extern crate glob;
extern crate protoc_rust;

use std::env;
use std::fs;
use std::fs::File;
use std::io::Write;
use std::path::Path;

use protoc_rust::Customize;

fn main() {
    // Generate protobuf files
    let proto_src_files = glob_simple("../../protos/*.proto");
    println!("{:?}", proto_src_files);

    let out_dir = env::var("OUT_DIR").expect("No OUT_DIR env variable");
    let dest_path = Path::new(&out_dir).join("messages");
    fs::create_dir_all(&dest_path).expect("Unable to create proto destination directory");

    let mod_file_content = proto_src_files
        .iter()
        .map(|proto_file| {
            let proto_path = Path::new(proto_file);
            format!(
                "pub mod {};",
                proto_path
                    .file_stem()
                    .expect("Unable to extract stem")
                    .to_str()
                    .expect("Unable to extract filename")
            )
        }).collect::<Vec<_>>()
        .join("\n");

    let mut mod_file = File::create(dest_path.join("mod.rs")).unwrap();
    mod_file
        .write_all(mod_file_content.as_bytes())
        .expect("Unable to write mod file");

    protoc_rust::run(protoc_rust::Args {
        out_dir: &dest_path.to_str().expect("Invalid proto destination path"),
        input: &proto_src_files
            .iter()
            .map(|a| a.as_ref())
            .collect::<Vec<&str>>(),
        includes: &["src", "../../protos"],
        customize: Customize::default(),
    }).expect("unable to run protoc");
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

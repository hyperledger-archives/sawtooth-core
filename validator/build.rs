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

use std::error::Error;
use std::fs;
use std::io::prelude::*;
use std::path::Path;

const PROTO_FILES_DIR: &str = "../protos";
const PROTOBUF_TARGET_DIR: &str = "src/proto";

fn main() {
    // Generate protobuf files
    let proto_src_files = glob_simple(&format!("{}/*.proto", PROTO_FILES_DIR));
    println!("{:?}", proto_src_files);

    fs::create_dir_all(PROTOBUF_TARGET_DIR).unwrap();

    protoc_rust::run(protoc_rust::Args {
        out_dir: PROTOBUF_TARGET_DIR,
        input: &proto_src_files
            .iter()
            .map(|&(_, ref a)| a)
            .map(|s| s.as_ref())
            .collect::<Vec<&str>>(),
        includes: &["src", PROTO_FILES_DIR],
    }).expect("unable to run protoc");

    let mod_file_name = format!("{}/mod.rs", PROTOBUF_TARGET_DIR);
    let mod_file_path = Path::new(&mod_file_name);
    let mut file = match fs::File::create(&mod_file_path) {
        Err(err) => panic!(
            "Unable to create file {}: {}",
            mod_file_name,
            err.description()
        ),
        Ok(file) => file,
    };

    let content = format!(
        r#"
/*
 * THIS IS A GENERATED FILE: DO NOT MODIFY
 *
 * This is the module which contains the generated sources for the Protocol
 * buffers messages.
 */

{}"#,
        proto_src_files
            .iter()
            .map(|&(ref module, _)| format!("pub mod {};", module))
            .collect::<Vec<_>>()
            .join("\n")
    );
    match file.write_all(content.as_bytes()) {
        Err(err) => panic!(
            "Unable to write to {}: {}",
            mod_file_name,
            err.description()
        ),
        Ok(_) => println!("generated {}", mod_file_name),
    }
}

fn glob_simple(pattern: &str) -> Vec<(String, String)> {
    glob::glob(pattern)
        .expect("glob")
        .map(|g| {
            let path = g.expect("item");

            let module_name = path.as_path()
                .file_stem()
                .expect("file stem")
                .to_str()
                .expect("utf-8")
                .to_owned();

            let file_path = path.as_path().to_str().expect("utf-8").to_owned();

            (module_name, file_path)
        })
        .collect()
}

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
use std::time::{Duration, UNIX_EPOCH};

use protoc_rust::Customize;

const PROTO_FILES_DIR: &str = "../protos";
const PROTOBUF_TARGET_DIR: &str = "src/proto";
const GENERATED_SOURCE_HEADER: &str = r#"
#![cfg_attr(rustfmt, rustfmt_skip)]

/*
 * THIS IS A GENERATED FILE: DO NOT MODIFY
 *
 * This is the module which contains the generated sources for the Protocol
 * buffers messages.
 */
"#;

#[derive(Debug, Clone)]
struct ProtoFile {
    module_name: String,
    file_path: String,
    last_modified: Duration,
}

fn main() {
    // Generate protobuf files
    let proto_src_files = glob_simple(&format!("{}/*.proto", PROTO_FILES_DIR));
    let last_build_time = read_last_build_time();

    let latest_change =
        proto_src_files
            .iter()
            .fold(Duration::from_secs(0), |max, ref proto_file| {
                if proto_file.last_modified > max {
                    proto_file.last_modified
                } else {
                    max
                }
            });

    if latest_change > last_build_time {
        println!("{:?}", proto_src_files);
        fs::create_dir_all(PROTOBUF_TARGET_DIR).unwrap();
        protoc_rust::run(protoc_rust::Args {
            out_dir: PROTOBUF_TARGET_DIR,
            input: &proto_src_files
                .iter()
                .map(|proto_file| proto_file.file_path.as_ref())
                .collect::<Vec<&str>>(),
            includes: &["src", PROTO_FILES_DIR],
            customize: Customize::default(),
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
            "{}\n{}\n",
            GENERATED_SOURCE_HEADER,
            proto_src_files
                .iter()
                .map(|proto_file| format!("pub mod {};", proto_file.module_name))
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
    } else {
        println!(
            "No proto files changed; latest modification: {}, last build: {}",
            latest_change.as_secs(),
            last_build_time.as_secs()
        );
    }
}

fn glob_simple(pattern: &str) -> Vec<ProtoFile> {
    glob::glob(pattern)
        .expect("Search did not result in files")
        .map(|g| protofile_info(g.expect("item").as_path()))
        .collect()
}

fn protofile_info(path: &Path) -> ProtoFile {
    let module_name = path
        .file_stem()
        .expect("Unable to get file stem")
        .to_str()
        .expect("File name should be utf-8")
        .to_owned();

    let file_path = path.to_str().expect("utf-8").to_owned();

    let file = fs::File::open(path).expect("Unable to open file");
    let last_modified = get_modified_time(file);

    ProtoFile {
        module_name,
        file_path,
        last_modified,
    }
}

fn read_last_build_time() -> Duration {
    let mod_file_name = format!("{}/mod.rs", PROTOBUF_TARGET_DIR);
    match fs::File::open(Path::new(&mod_file_name)) {
        Err(err) => {
            println!(
                "unable to open {}: {}; defaulting to 0",
                mod_file_name,
                err.description()
            );
            Duration::new(0, 0)
        }
        Ok(file) => get_modified_time(file),
    }
}

fn get_modified_time(file: fs::File) -> Duration {
    file.metadata()
        .expect("File should have metadata")
        .modified()
        .map(|sys_time| {
            sys_time
                .duration_since(UNIX_EPOCH)
                .expect("System time should be after UNIX_EPOCH")
        }).expect("File should have modified time")
}

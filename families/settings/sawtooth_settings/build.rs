/*
 * Copyright 2018 Bitwise IO, Inc.
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
use std::env;
use std::fs;
use std::io::Write;
use std::path::Path;

const PROTO_DIR_NAME: &str = "protos";

fn main() {
    let out_dir = env::var("OUT_DIR").expect("No OUT_DIR env variable");
    let dest_path = Path::new(&out_dir).join(PROTO_DIR_NAME);

    let mut proto_src_files = glob_simple("../protos/*.proto");
    let main_proto_src_files = glob_simple("../../../protos/*.proto");
    proto_src_files.extend(main_proto_src_files);

    println!("{:?}", proto_src_files);

    fs::create_dir_all(&dest_path).expect("Unable to create protobuf out dir");
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
        })
        .collect::<Vec<_>>()
        .join("\n");
    let mut mod_file = fs::File::create(dest_path.join("mod.rs")).unwrap();
    mod_file
        .write_all(mod_file_content.as_bytes())
        .expect("Unable to write mod file");

    protoc_rust::Codegen::new()
        .out_dir(
            &dest_path
                .to_str()
                .expect("Unable to create 'dest_path' as str"),
        )
        .inputs(
            &proto_src_files
                .iter()
                .map(|a| a.as_ref())
                .collect::<Vec<&str>>(),
        )
        .includes(&["../protos", "../../../protos"])
        .customize(Customize {
            ..Default::default()
        })
        .run()
        .expect("Error generating rust files from settings protos");
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
        })
        .collect()
}

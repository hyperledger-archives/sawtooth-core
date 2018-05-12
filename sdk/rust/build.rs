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

extern crate cc;
extern crate glob;
extern crate protoc_rust;

use std::fs;

use protoc_rust::Customize;

fn main() {
    // Compile C PEM loader file
    if cfg!(feature = "pem") {
        println!("cargo:rustc-link-lib={}={}", "dylib", "crypto");
        cc::Build::new()
            .file("../c/loader.c")
            .file("../c/c11_support.c")
            .include("../c")
            .compile("libloader.a");
    }

    // Generate protobuf files
    let proto_src_files = glob_simple("../../protos/*.proto");
    println!("{:?}", proto_src_files);

    fs::create_dir_all("src/messages").unwrap();

    protoc_rust::run(protoc_rust::Args {
        out_dir: "src/messages",
        input: &proto_src_files
            .iter()
            .map(|a| a.as_ref())
            .collect::<Vec<&str>>(),
        includes: &["src", "../../protos"],
        customize: Customize {
            ..Default::default()
        },
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
        })
        .collect()
}

#![feature(try_trait)]
#![feature(custom_attribute)]
#[macro_use] extern crate failure_derive;
#[macro_use] extern crate clap;
#[macro_use] extern crate serde_derive;
extern crate serde;
extern crate serde_json;
extern crate serde_cbor;
extern crate crypto;
extern crate protobuf;
extern crate hyper;
extern crate futures;
extern crate tokio_core;
extern crate base64;
extern crate users;
extern crate sawtooth_sdk;
extern crate failure;
//extern crate term;

use clap::{ App, Arg };
use errors::IntkeyError;
use getstate::get_state;
use maketx::build_and_exec;

mod errors;
mod maketx;
mod keymgmt;
mod makebatch;
mod submitbatch;
mod getstate;


fn run() -> Result<(), IntkeyError> {
    let matches = App::new("Intkey CLI Implementation in Rust")
                        .version(crate_version!())
                        .author(crate_authors!())
                        .about("sawtooth intkey client in rust")

                        .arg(Arg::with_name("verb")
                            .help("can 'set' a new value, 'inc'rement, 'dec'rement, show one value by key, or list all values"))

                        .arg(Arg::with_name("key_name")
                            .help("The name of your key"))
                        
                        .arg(Arg::with_name("assigned_value")
                            .help("the value you want to assign, increment by, or decrement by"))
                        
                        .arg(Arg::with_name("keyfile")
                            .short("k")
                            .long("keyfile")
                            .value_name("keyfile")
                            .help("Specify name of signing key. Defaults to your environment username. Enter as -k <name> for <name>.priv.")
                            .takes_value(true))

                        .arg(Arg::with_name("url")
                            .short("u")
                            .long("url")
                            .value_name("url")
                            .help("specify REST API url. Defaults to local host.")
                            .takes_value(true))

                        
                .get_matches();

    match matches.value_of("verb") {
        Some("list") => get_state(matches.value_of("url"), None)?,
        Some("show") => get_state(matches.value_of("url"), matches.value_of("key_name"))?,
        Some("set") => build_and_exec("set",
                                              matches.value_of("key_name")?,
                                              matches.value_of("assigned_value")?,
                                              matches.value_of("keyfile"),
                                              matches.value_of("url"))?,
        Some("inc") => build_and_exec("inc",
                                              matches.value_of("key_name")?,
                                              matches.value_of("assigned_value")?,
                                              matches.value_of("keyfile"),
                                              matches.value_of("url"))?,
        Some("dec") => build_and_exec("dec",
                                              matches.value_of("key_name")?,
                                              matches.value_of("assigned_value")?,
                                              matches.value_of("keyfile"),
                                              matches.value_of("url"))?,
        _ => return Err(IntkeyError::ParsedNoneError)

    };

        Ok(())
}


fn main() {
    if let Err(e) = run() {
        println!("{}", e);
        std::process::exit(1);
    }
}

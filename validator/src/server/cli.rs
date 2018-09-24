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

use clap::{App, Arg, ArgMatches};
use cpython::{PyDict, PyResult, Python};

const DISTRIBUTION_NAME: &str = "sawtooth-validator";
const VERSION: &str = env!("CARGO_PKG_VERSION");

pub fn wrap_in_pydict(py: Python, matches: &ArgMatches) -> PyResult<PyDict> {
    let (bind_component, bind_network, bind_consensus) = parse_bindings(matches);

    let pydict = PyDict::new(py);

    pydict.set_item(py, "bind_component", bind_component)?;
    pydict.set_item(py, "bind_network", bind_network)?;
    pydict.set_item(py, "bind_consensus", bind_consensus)?;
    pydict.set_item(py, "config_dir", matches.value_of("config_dir"))?;
    pydict.set_item(py, "endpoint", matches.value_of("endpoint"))?;
    pydict.set_item(
        py,
        "maximum_peer_connectivity",
        matches
            .value_of("maximum_peer_connectivity")
            .and_then(|s| s.parse::<u32>().ok()),
    )?;
    pydict.set_item(
        py,
        "minimum_peer_connectivity",
        matches
            .value_of("minimum-peer-connectivity")
            .and_then(|s| s.parse::<u32>().ok()),
    )?;
    pydict.set_item(py, "opentsdb_db", matches.value_of("opentsdb-db"))?;
    pydict.set_item(py, "opentsdb_url", matches.value_of("opentsdb-url"))?;
    pydict.set_item(py, "peering", matches.value_of("peering"))?;
    pydict.set_item(py, "peers", parse_comma_separated_args("peers", matches))?;
    pydict.set_item(py, "roles", parse_roles(matches, py))?;
    pydict.set_item(py, "scheduler", matches.value_of("scheduler"))?;
    pydict.set_item(py, "seeds", parse_comma_separated_args("seeds", matches))?;
    pydict.set_item(py, "verbose", matches.occurrences_of("verbose"))?;
    pydict.set_item(
        py,
        "state_pruning_block_depth",
        matches
            .value_of("state_pruning_block_depth")
            .and_then(|s| s.parse::<u32>().ok()),
    )?;

    Ok(pydict)
}

pub fn parse_args<'a>() -> ArgMatches<'a> {
    let app = App::new(DISTRIBUTION_NAME)
        .version(VERSION)
        .about("Configures and starts a Sawtooth validator.")
        .arg(
            Arg::with_name("config_dir")
                .long("config-dir")
                .takes_value(true)
                .help("specify the configuration directory"),
        ).arg(
            Arg::with_name("bind")
                .short("B")
                .long("bind")
                .takes_value(true)
                .multiple(true)
                .help(
                    "set the URL for the network or validator \
                     component service endpoints with the format \
                     network:<endpoint>, component:<endpoint>, or \
                     consensus:<endpoint>. Use multiple --bind options \
                     to specify all endpoints.",
                ),
        ).arg(
            Arg::with_name("peering")
                .short("P")
                .long("peering")
                .takes_value(true)
                .possible_values(&["static", "dynamic"])
                .help(
                    "determine peering type for the validator: \
                     'static' (must use --peers to list peers) or \
                     'dynamic' (processes any static peers first, \
                     then starts topology buildout).",
                ),
        ).arg(
            Arg::with_name("endpoint")
                .short("E")
                .long("endpoint")
                .takes_value(true)
                .help("specifies the advertised network endpoint URL"),
        ).arg(
            Arg::with_name("seeds")
                .short("s")
                .long("seeds")
                .takes_value(true)
                .multiple(true)
                .help(
                    "provide URI(s) for the initial connection to \
                     the validator network, in the format \
                     tcp://<hostname>:<port>. Specify multiple URIs \
                     in a comma-separated list. Repeating the --seeds \
                     option is also accepted.",
                ),
        ).arg(
            Arg::with_name("peers")
                .short("p")
                .long("peers")
                .takes_value(true)
                .multiple(true)
                .help(
                    "list static peers to attempt to connect to \
                     in the format tcp://<hostname>:<port>. Specify \
                     multiple peers in a comma-separated list. \
                     Repeating the --peers option is also accepted.",
                ),
        ).arg(
            Arg::with_name("verbose")
                .short("v")
                .long("verbose")
                .multiple(true)
                .help("enable more verbose output to stderr"),
        ).arg(
            Arg::with_name("scheduler")
                .long("scheduler")
                .takes_value(true)
                .possible_values(&["serial", "parallel"])
                .help("set scheduler type: serial or parallel"),
        ).arg(
            Arg::with_name("network_auth")
                .long("network-auth")
                .takes_value(true)
                .possible_values(&["trust", "challenge"])
                .help(
                    "identify type of authorization required to join validator \
                     network.",
                ),
        ).arg(
            Arg::with_name("opentsdb-url")
                .long("opentsdb-url")
                .takes_value(true)
                .help(
                    "specify host and port for Open TSDB database used for \
                     metrics",
                ),
        ).arg(
            Arg::with_name("opentsdb-db")
                .long("opentsdb-db")
                .takes_value(true)
                .help("specify name of database used for storing metrics"),
        ).arg(
            Arg::with_name("minimum_peer_connectivity")
                .long("minimum-peer-connectivity")
                .takes_value(true)
                .validator(is_positive_integer)
                .help(
                    "set the minimum number of peers required before stopping \
                     peer search",
                ),
        ).arg(
            Arg::with_name("maximum_peer_connectivity")
                .long("maximum-peer-connectivity")
                .takes_value(true)
                .validator(is_positive_integer)
                .help("set the maximum number of peers to accept"),
        ).arg(
            Arg::with_name("state_pruning_block_depth")
                .long("state-pruning-block-depth")
                .takes_value(true)
                .validator(is_positive_integer)
                .help(
                    "set the block depth below which state roots are \
                     pruned from the global state database.",
                ),
        );

    app.get_matches()
}

fn is_positive_integer(arg_value: String) -> Result<(), String> {
    match arg_value.parse::<u32>() {
        Ok(i) if i > 0 => Ok(()),
        _ => Err("The value must be a positive number, greater than 0".into()),
    }
}

fn parse_roles<'a>(matches: &'a ArgMatches, py: Python) -> Option<PyDict> {
    match matches.value_of("network_auth") {
        Some(network_auth) => {
            let auth_dict = PyDict::new(py);
            auth_dict.set_item(py, "network", network_auth).unwrap();
            Some(auth_dict)
        }
        None => None,
    }
}

fn parse_bindings<'a>(
    matches: &'a ArgMatches,
) -> (Option<&'a str>, Option<&'a str>, Option<&'a str>) {
    let mut bind_network = None;
    let mut bind_component = None;
    let mut bind_consensus = None;

    if let Some(bindings) = parse_multiple_args("bind", matches) {
        for binding in bindings {
            if binding.starts_with("network") {
                bind_network = Some(binding.splitn(2, ':').skip(1).collect::<Vec<_>>()[0]);
            }

            if binding.starts_with("component") {
                bind_component = Some(binding.splitn(2, ':').skip(1).collect::<Vec<_>>()[0]);
            }

            if binding.starts_with("consensus") {
                bind_consensus = Some(binding.splitn(2, ':').skip(1).collect::<Vec<_>>()[0]);
            }
        }
    };

    (bind_component, bind_network, bind_consensus)
}

fn parse_comma_separated_args(name: &str, matches: &ArgMatches) -> Option<Vec<String>> {
    parse_multiple_args(name, matches).map(|arglist| {
        arglist
            .join(",")
            .split(',')
            .map(String::from)
            .collect::<Vec<String>>()
    })
}

fn parse_multiple_args<'a>(name: &str, matches: &'a ArgMatches) -> Option<Vec<&'a str>> {
    matches.values_of(name).map(|vals| vals.collect())
}

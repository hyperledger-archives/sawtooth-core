// Copyright 2018 Bitwise IO, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

extern crate battleship;
#[macro_use]
extern crate clap;
#[macro_use]
extern crate failure;
#[macro_use]
extern crate prettytable;
extern crate sawtooth_sdk;
extern crate users;

use battleship::client::BattleshipClient;
use battleship::game::Board;
use clap::ArgMatches;
use failure::Error;
use prettytable::format::consts::FORMAT_NO_BORDER_LINE_SEPARATOR;
use prettytable::Table;

/// Parses an optional wait argument that can be used as a simple flag, or an option
/// Example CLI usages:
///   <elided>      // If left out completely, returns None
///   -w            // If passed in as just a flag, returns Option<60>
///   -w 42         // If passed in with a value, returns Option<value>
/// The latter two cases are also coerced into the correct type
fn parse_wait_flag(matches: &ArgMatches) -> Result<Option<u64>, Error> {
    if matches.is_present("wait") {
        let val = matches.value_of("wait");
        match val.or(Some("60")).and_then(|w| w.parse::<u64>().ok()) {
            Some(arg) => Ok(Some(arg)),
            None => Err(format_err!(
                "Bad value for wait: `{}`",
                val.expect("Wait must exist!")
            ))?,
        }
    } else {
        Ok(None)
    }
}

fn run() -> Result<(), Error> {
    let matches = clap_app!(myapp =>
        (name: crate_name!())
        (version: crate_version!())
        (about: crate_description!())
        (@setting SubcommandRequiredElseHelp)
        (@arg url: --url +takes_value "URL to the Sawtooth REST API")
        (@arg key: -k --key +takes_value "Signing key used for player identification")
        (@subcommand create =>
            (about: "Create Battleship game")
            (@arg name: +required "Name of the game to create")
            (@arg ships: "Ships to place on the board")
            (@arg wait: -w --wait +takes_value min_values(0) max_values(1) ...
                "Number of seconds to wait for transaction to complete")
        )
        (@subcommand join =>
            (about: "Join Battleship game")
            (@arg name: +required "Name of the game to create")
            (@arg wait: -w --wait +takes_value min_values(0) max_values(1) ...
                "Number of seconds to wait for transaction to complete")
        )
        (@subcommand fire =>
            (about: "Fire a shot in a Battleship game")
            (@arg name: +required "Name of the game to create")
            (@arg row: +required "Row to fire on")
            (@arg col: +required "Column to fire on")
            (@arg wait: -w --wait +takes_value min_values(0) max_values(1) ...
                "Number of seconds to wait for transaction to complete")
        )
        (@subcommand list =>
            (about: "List Battleship games")
        )
        (@subcommand show =>
            (about: "Show Battleship games")
            (@arg name: +required "Name of the game to show")
        )
    )
    .get_matches();

    let url = matches.value_of("url").unwrap_or("http://localhost:8008/");

    let current_user =
        users::get_current_username().ok_or_else(|| format_err!("Couldn't get current user!"))?;

    let key = matches.value_of("key").unwrap_or_else(|| {
        current_user
            .to_str()
            .expect("Unable to convert current user to str")
    });
    let client = BattleshipClient::new(url, key)?;

    match matches.subcommand() {
        ("create", Some(create_matches)) => {
            let name = create_matches.value_of("name").expect("Name is required!");
            let ships = create_matches
                .value_of("ships")
                .unwrap_or("AAAAA,BBBB,CCC,DD,DD,SSS,SSS")
                .split(',')
                .map(String::from)
                .collect();
            let wait = parse_wait_flag(create_matches)?;

            let link = client.create(name, ships)?;

            match wait {
                Some(w) => {
                    client.wait(&link, w)?;
                    println!("Created game `{}`.", name);
                }
                None => println!(
                    "Transaction successfully submitted to create game `{}`.",
                    name
                ),
            }
        }
        ("join", Some(join_matches)) => {
            let name = join_matches.value_of("name").expect("Name is required!");
            let wait = parse_wait_flag(join_matches)?;

            let games = client.list()?;
            let game = games
                .get(name)
                .ok_or_else(|| format_err!("Couldn't get game `{}`!", name))?;
            let board = Board::load_or_generate(format!("{}-{}", name, key), &game.ships)?;

            let link = client.join(name, board.render_hashed())?;

            match wait {
                Some(w) => {
                    client.wait(&link, w)?;
                    println!("Joined game `{}`.", name);
                }
                None => println!(
                    "Transaction successfully submitted to join game `{}`.",
                    name
                ),
            }
        }
        ("fire", Some(fire_matches)) => {
            let name = fire_matches.value_of("name").expect("Name is required!");
            let row = fire_matches.value_of("row").expect("Row is required!");
            let col = fire_matches.value_of("col").expect("Column is required!");
            let wait = parse_wait_flag(fire_matches)?;

            let game = client.get_game(&name)?;
            let board = Board::load_or_generate(format!("{}-{}", name, key), &game.ships)?;
            let (reveal_space, reveal_nonce) = game.get_last_fire_row_col(&board)?;

            let link = client.fire(name, row, col, reveal_space, reveal_nonce)?;

            match wait {
                Some(w) => {
                    client.wait(&link, w)?;
                    println!("Fired on {}{} in game `{}`.", row, col, name);
                }
                None => println!(
                    "Transaction successfully submitted to fire on {} {} in game `{}`.",
                    row, col, name
                ),
            }
        }
        ("list", _) => {
            let games = client.list()?;

            let mut table = Table::new();
            table.set_format(*FORMAT_NO_BORDER_LINE_SEPARATOR);

            table.set_titles(row!["NAME", "PLAYER 1", "PLAYER 2", "STATE"]);

            for (name, game) in games {
                table.add_row(row![
                    name,
                    game.player_1.unwrap_or_else(String::new),
                    game.player_2.unwrap_or_else(String::new),
                    game.state
                ]);
            }

            table.printstd();
        }
        ("show", Some(show_matches)) => {
            let name = show_matches.value_of("name").expect("Name is required!");

            let games = client.list()?;
            let game = games
                .get(name)
                .ok_or_else(|| format_err!("Couldn't get game `{}`!", name))?;
            let board = Board::load(&format!("{}-{}", name, key)).ok();
            let pub_key = client.pub_key()?;

            fn board_to_str(board: &[Vec<char>]) -> String {
                board
                    .iter()
                    .map(|row| {
                        row.iter()
                            .map(|&i| if i == '?' { '.' } else { i })
                            .collect::<String>()
                    })
                    .collect::<Vec<_>>()
                    .join("\n")
            }

            // Shows your board, but with any hits and misses overlaid
            fn overlay_boards(board1: &[Vec<char>], board2: &[Vec<char>]) -> Vec<Vec<char>> {
                board1
                    .iter()
                    .zip(board2)
                    .map(|(r1, r2)| {
                        r1.iter()
                            .zip(r2)
                            .map(|(&i1, &i2)| if i2 == '?' { i1 } else { i2 })
                            .collect()
                    })
                    .collect()
            }

            println!("Game State:\n{}\n", game.state);
            println!(
                "Player #1: {}",
                game.player_1
                    .clone()
                    .or_else(|| Some("<none>".into()))
                    .unwrap()
            );
            println!(
                "Player #2: {}\n",
                game.player_2
                    .clone()
                    .or_else(|| Some("<none>".into()))
                    .unwrap()
            );

            match (
                game.player_1 == Some(pub_key.clone()),
                game.player_2 == Some(pub_key.clone()),
                board,
            ) {
                (true, true, _) => Err(format_err!("You can't play with yourself!"))?,
                (false, false, _) => {
                    println!("Board #1:\n{}\n", board_to_str(&game.target_board_1));
                    println!("Board #2:\n{}", board_to_str(&game.target_board_2));
                }
                (true, false, Some(b)) => {
                    println!(
                        "Your Board:\n{}\n",
                        board_to_str(&overlay_boards(&b.spaces, &game.target_board_1))
                    );
                    println!("Opponent's Board:\n{}", board_to_str(&game.target_board_2));
                }
                (false, true, Some(b)) => {
                    println!(
                        "Your Board:\n{}\n",
                        board_to_str(&overlay_boards(&b.spaces, &game.target_board_2))
                    );
                    println!("Opponent's Board:\n{}", board_to_str(&game.target_board_1));
                }
                (true, false, None) | (false, true, None) => {
                    println!("Couldn't load board for `{}`!", key);
                }
            }
        }
        _ => println!("other"),
    }

    Ok(())
}

fn main() {
    // Attempt to run command, and print out any errors encountered
    if let Err(e) = run() {
        eprint!("Error: {}", e);
        let mut e = e.as_fail();
        while let Some(cause) = e.cause() {
            eprint!(", {}", cause);
            e = cause;
        }
        eprintln!();
        std::process::exit(1);
    }
}

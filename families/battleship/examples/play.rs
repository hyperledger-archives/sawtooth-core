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
extern crate failure;
extern crate rand;
extern crate sawtooth_sdk;

use battleship::client::BattleshipClient;
use battleship::game::Board;
use failure::Error;
use rand::distributions::Alphanumeric;
use rand::{thread_rng, Rng};
use sawtooth_sdk::signing::create_context;

fn main() -> Result<(), Error> {
    let name: String = thread_rng().sample_iter(&Alphanumeric).take(10).collect();
    let wait = 60;
    let ships: Vec<String> = "AAAAA,BBBB,CCC,DD,DD,SSS,SSS"
        .split(",")
        .map(String::from)
        .collect();

    println!("Creating game {} with ships {}.\n", name, ships.join(","));

    let context = create_context("secp256k1").unwrap();
    let key1 = context.new_random_private_key().unwrap();
    let key2 = context.new_random_private_key().unwrap();

    let client1 = BattleshipClient::new_with_key("http://localhost:8008/", key1)?;
    let client2 = BattleshipClient::new_with_key("http://localhost:8008/", key2)?;

    let board1 = Board::generate(&ships);
    let board2 = Board::generate(&ships);

    println!("Player 1's board:\n{}\n", board1.render());
    println!("Player 2's board:\n{}\n", board2.render());

    client1.wait(&client1.create(&name, ships)?, wait)?;
    client1.wait(&client1.join(&name, board1.render_hashed())?, wait)?;
    client2.wait(&client2.join(&name, board2.render_hashed())?, wait)?;

    'outer: for i in 0u8..10 {
        for j in 0u8..10 {
            let row = (('A' as u8 + i) as char).to_string();
            let col = (j + 1).to_string();

            println!("Player 1 firing upon {} {}", row, col);
            let game = client1.get_game(&name)?;

            match game.state.as_str() {
                "P1-WIN" | "P2-WIN" => {
                    break 'outer;
                }
                _ => {}
            }

            let (reveal_space, reveal_nonce) = game.get_last_fire_row_col(&board1)?;
            client1.wait(
                &client1.fire(&name, &row, &col, reveal_space, reveal_nonce)?,
                wait,
            )?;

            println!("Player 2 firing upon {} {}", row, col);
            let game = client2.get_game(&name)?;

            match game.state.as_str() {
                "P1-WIN" | "P2-WIN" => {
                    break 'outer;
                }
                _ => {}
            }

            let (reveal_space, reveal_nonce) = game.get_last_fire_row_col(&board2)?;
            client2.wait(
                &client2.fire(&name, &row, &col, reveal_space, reveal_nonce)?,
                wait,
            )?;
        }
    }

    let game = client2.get_game(&name)?;
    println!("Game complete!");
    println!("State: {}", game.state);

    Ok(())
}

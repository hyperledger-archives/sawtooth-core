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

use crypto::digest::Digest;
use crypto::sha2::Sha512;
use dirs::home_dir;
use failure::Error;
use rand::distributions::Alphanumeric;
use rand::{thread_rng, Rng};
use serde_json;
use std::fs::File;
use std::path::PathBuf;

// Convenience functions

/// Convenience function for calculating prefix for the `battleship` transaction family
pub fn get_battleship_prefix() -> String {
    let mut sha = Sha512::new();
    sha.input_str("battleship");
    sha.result_str()[..6].to_string()
}

/// Hash the name of a game of battleship
/// Used for calculating the state address that state for a given game is stored at
pub fn get_battleship_name_hash(name: &str) -> String {
    let mut sha = Sha512::new();
    sha.input_str(name);
    sha.result_str()[..64].to_string()
}

/// Get a state address for a given game of battleship
pub fn get_battleship_address(name: &str) -> String {
    vec![get_battleship_prefix(), get_battleship_name_hash(name)].join("")
}

/// Hash the value and nonce for a revealed space
/// When a player joins, we're given a hashed board of their ship locations.
/// On each player's turn, they give us a nonce and the value of that space,
/// e.g. `'-'` and `"g54h45hwer"`. We hash those together and compare against
/// the given hashed board to ensure that the player didn't lie about where
/// their ships were located.
pub fn get_space_hash(space: char, nonce: &str) -> String {
    let mut sha = Sha512::new();
    sha.input_str(nonce);
    sha.input_str(&space.to_string());
    sha.result_str()
}

/// Parses a column value such as "1" to be a numerical column value
/// Returns `None` if parsed number isn't in `[0, 10)`.
pub fn parse_column(col: &str) -> Option<usize> {
    match col.parse::<usize>().ok()?.checked_sub(1) {
        Some(num @ 0..=9) => Some(num),
        _ => None,
    }
}

/// Parses a row value such as "B" to be a numerical row value.
/// Drops characters other than the first while parsing, and returns
/// `None` if parsed number isn't in `[0, 10)`.
pub fn parse_row(row: &str) -> Option<usize> {
    match (row.chars().next()? as usize).checked_sub('A' as usize) {
        Some(num @ 0..=9) => Some(num),
        _ => None,
    }
}

// Game structs

/// A game as it is stored on-chain.
///
/// Does not store the actual location of ships on each player's board. Instead,
/// it stores a hash of each space that is created from the space value and a unique
/// nonce for that space. When each player fires, they are required to reveal the space's
/// value that was last fired upon by their opponent, as well as the nonce used to
/// generate the hash for that space. The transaction processor then hashes those values
/// and checks it against the hash it received for the space when the player joined the game.
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Game {
    #[serde(rename = "State")]
    pub state: String,
    #[serde(rename = "Ships")]
    pub ships: Vec<String>,
    #[serde(rename = "Player1")]
    pub player_1: Option<String>,
    #[serde(rename = "HashedBoard1")]
    pub hashed_board_1: Vec<Vec<String>>,
    #[serde(rename = "TargetBoard1")]
    pub target_board_1: Vec<Vec<char>>,
    #[serde(rename = "Player2")]
    pub player_2: Option<String>,
    #[serde(rename = "HashedBoard2")]
    pub hashed_board_2: Vec<Vec<String>>,
    #[serde(rename = "TargetBoard2")]
    pub target_board_2: Vec<Vec<char>>,
    #[serde(rename = "LastFireColumn")]
    pub last_fire_column: Option<String>,
    #[serde(rename = "LastFireRow")]
    pub last_fire_row: Option<String>,
}

impl Game {
    /// Gets the last row and column that were fired upon.
    ///
    /// Both optional due to the first turn not having had any previous firings
    pub fn get_last_fire_row_col(
        &self,
        board: &Board,
    ) -> Result<(Option<char>, Option<String>), Error> {
        let last_row = self.clone().last_fire_row.and_then(|lfr| parse_row(&lfr));
        let last_col = self
            .clone()
            .last_fire_column
            .and_then(|lfc| parse_column(&lfc));

        Ok(match (last_row, last_col) {
            (Some(row), Some(col)) => (
                Some(board.spaces[row][col]),
                Some(board.nonces[row][col].clone()),
            ),
            (None, None) => (None, None),
            (Some(_), None) | (None, Some(_)) => Err(format_err!("Game is in invalid state!"))?,
        })
    }
}

impl Default for Game {
    fn default() -> Game {
        Game {
            state: String::from("NEW"),
            ships: vec![],
            player_1: None,
            hashed_board_1: vec![],
            target_board_1: vec![],
            player_2: None,
            hashed_board_2: vec![],
            target_board_2: vec![],
            last_fire_column: None,
            last_fire_row: None,
        }
    }
}

/// An action that updates a `Game`.
#[derive(Serialize, Deserialize, Debug)]
#[serde(tag = "Action")]
pub enum Action {
    #[serde(rename = "CREATE")]
    Create {
        #[serde(rename = "Name")]
        name: String,
        #[serde(rename = "Ships")]
        ships: Vec<String>,
    },
    #[serde(rename = "JOIN")]
    Join {
        #[serde(rename = "Name")]
        name: String,
        #[serde(rename = "Board")]
        board: Vec<Vec<String>>,
    },
    #[serde(rename = "FIRE")]
    Fire {
        #[serde(rename = "Name")]
        name: String,
        #[serde(rename = "Column")]
        column: String,
        #[serde(rename = "Row")]
        row: String,
        #[serde(rename = "RevealSpace")]
        reveal_space: Option<char>,
        #[serde(rename = "RevealNonce")]
        reveal_nonce: Option<String>,
    },
}

/// A player's game board.
///
/// Stored as a JSON file in `~/.sawtooth/battleship/$GAME-$PLAYER.json`
#[derive(Default, Debug, Serialize, Deserialize)]
pub struct Board {
    pub spaces: Vec<Vec<char>>,
    pub nonces: Vec<Vec<String>>,
}

impl Board {
    fn with_size(rows: usize, cols: usize) -> Self {
        let mut rng = thread_rng();
        let nonces = (0..rows)
            .map(|_| {
                (0..cols)
                    .map(|_| rng.sample_iter(&Alphanumeric).take(10).collect())
                    .collect()
            })
            .collect();

        let spaces = (0..rows)
            .map(|_| (0..cols).map(|_| '-').collect())
            .collect();

        Self { spaces, nonces }
    }

    /// Loads a board with the given name from disk.
    pub fn load(name: &str) -> Result<Self, Error> {
        let mut path = Self::get_conf_dir().ok_or_else(|| format_err!("Couldn't get conf dir!"))?;

        if !path.is_dir() {
            Err(format_err!(
                "The path `{}` could not be found!",
                path.display()
            ))?
        }

        path.push(name);
        path.set_extension("json");

        File::open(&path)
            .map(|f| serde_json::from_reader(f).map_err(|e| format_err!("{}", e)))
            .map_err(|e| format_err!("{}", e))?
    }

    /// Generates a board by arranging the given ships
    pub fn generate(ships: &[String]) -> Self {
        let mut rng = thread_rng();
        let (rows, cols) = (10usize, 10usize);
        let mut board = Self::with_size(rows, cols);

        for ship in ships {
            let length = ship.chars().count();

            'outer: loop {
                let row = rng.gen_range(0, rows);
                let col = rng.gen_range(0, cols);
                let is_vertical = rng.gen_bool(0.5);

                if is_vertical {
                    if row + length >= rows {
                        continue;
                    }

                    for (i, _) in ship.chars().enumerate() {
                        if board.spaces[row + i][col] != '-' {
                            continue 'outer;
                        }
                    }

                    for (i, ch) in ship.chars().enumerate() {
                        board.spaces[row + i][col] = ch;
                    }
                    break;
                } else {
                    if col + length >= cols {
                        continue;
                    }

                    for (i, _) in ship.chars().enumerate() {
                        if board.spaces[row][col + i] != '-' {
                            continue 'outer;
                        }
                    }

                    for (i, ch) in ship.chars().enumerate() {
                        board.spaces[row][col + i] = ch;
                    }
                    break;
                }
            }
        }

        board
    }

    fn get_conf_dir() -> Option<PathBuf> {
        let home = home_dir()?;

        Some([home.to_str()?, ".sawtooth", "battleship"].iter().collect())
    }

    /// Attempts to load the given board, and generates it if it doesn't exist
    pub fn load_or_generate(name: String, ships: &[String]) -> Result<Self, Error> {
        let mut path = Self::get_conf_dir().ok_or_else(|| format_err!("Couldn't get conf dir!"))?;

        if !path.is_dir() {
            Err(format_err!(
                "The path `{}` could not be found!",
                path.display()
            ))?
        }

        path.push(name);
        path.set_extension("json");

        match File::open(&path) {
            Ok(f) => Ok(serde_json::from_reader(f).map_err(|e| format_err!("{}", e))?),
            Err(_) => {
                let board = Self::generate(ships);
                let f = File::create(path)?;
                serde_json::to_writer(f, &board)?;
                Ok(board)
            }
        }
    }

    /// Calculates `hash(space, nonce) for each space/nonce pair
    pub fn render_hashed(&self) -> Vec<Vec<String>> {
        self.spaces
            .iter()
            .zip(&self.nonces)
            .map(|(spaces_row, nonces_row)| {
                spaces_row
                    .iter()
                    .zip(nonces_row)
                    .map(|(space, nonce)| get_space_hash(*space, nonce))
                    .collect()
            })
            .collect()
    }

    /// Converts the board's spaces to a human-friendly format
    pub fn render(&self) -> String {
        self.spaces
            .iter()
            .map(|ref row| row.iter().collect::<String>())
            .collect::<Vec<_>>()
            .join("\n")
    }
}

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
 * -----------------------------------------------------------------------------
 */

use std::collections::HashMap;

use sawtooth_sdk::processor::handler::ApplyError;

const POSSIBLE_WINS: [(usize, usize, usize); 8] = [
    (1, 2, 3),
    (4, 5, 6),
    (7, 8, 9),
    (1, 4, 7),
    (2, 5, 8),
    (3, 6, 9),
    (1, 5, 9),
    (3, 5, 7),
];

#[derive(Debug, Clone)]
pub struct Game {
    name: String,
    board: String,
    game_state: String,
    player1: String,
    player2: String,
    player1_short: String,
    player2_short: String,
}

impl Game {
    pub fn new(name: String) -> Game {
        Game {
            name: name,
            board: "-".repeat(9),
            game_state: String::from("P1-NEXT"),
            player1: String::from(""),
            player2: String::from(""),
            player1_short: String::from(""),
            player2_short: String::from(""),
        }
    }

    fn to_string(&self) -> String {
        let fields = vec![
            self.name.clone(),
            self.board.clone(),
            self.game_state.clone(),
            self.player1.clone(),
            self.player2.clone(),
        ];
        fields.join(",")
    }

    fn from_string(game_string: String) -> Option<Game> {
        let items: Vec<&str> = game_string.split(",").collect();
        if items.len() != 5 {
            return None;
        }
        let mut g = Game {
            name: items[0].to_string(),
            board: items[1].to_string(),
            game_state: items[2].to_string(),
            player1: String::from(""),
            player2: String::from(""),
            player1_short: String::from(""),
            player2_short: String::from(""),
        };
        g.set_player1(items[3]);
        g.set_player2(items[4]);
        Some(g)
    }

    pub fn serialize_games(games: HashMap<String, Game>) -> String {
        let mut game_strings: Vec<String> = vec![];
        for (_, game) in games {
            game_strings.push(game.to_string().clone());
        }
        game_strings.sort();
        game_strings.join("|")
    }

    pub fn deserialize_games(games_string: String) -> Option<HashMap<String, Game>> {
        let mut ret: HashMap<String, Game> = HashMap::new();
        let game_string_list: Vec<&str> = games_string.split("|").collect();
        for g in game_string_list {
            let game = Game::from_string(g.to_string());
            match game {
                Some(game_item) => ret.insert(game_item.name.clone(), game_item),
                None => return None,
            };
        }
        Some(ret)
    }

    pub fn mark_space(&mut self, space: usize) -> Result<(), ApplyError> {
        let mark = match self.game_state.as_str() {
            "P1-NEXT" => "X",
            "P2-NEXT" => "O",
            other_state => {
                return Err(ApplyError::InvalidTransaction(String::from(format!(
                    "Invalid state {}",
                    other_state
                ))))
            }
        };

        let index = space - 1;

        let board_vec: Vec<String> = self
            .board
            .chars()
            .enumerate()
            .map(|(i, ch)| {
                if i == index {
                    mark.to_string()
                } else {
                    ch.to_string()
                }
            }).collect();
        self.board = board_vec.join("");
        Ok(())
    }

    pub fn update_state(&mut self) -> Result<(), ApplyError> {
        let x_wins = self.is_win("X");
        let o_wins = self.is_win("O");

        let winner = match (x_wins, o_wins) {
            (true, true) => {
                return Err(ApplyError::InvalidTransaction(String::from(
                    "Two winners (there can only be one)",
                )))
            }
            (true, false) => Some(String::from("P1-WIN")),
            (false, true) => Some(String::from("P2-WIN")),
            _ => None,
        };

        if let Some(w) = winner {
            self.game_state = w;
            return Ok(());
        }

        if !self.board.contains("-") {
            self.game_state = String::from("TIE");
            return Ok(());
        }

        if self.game_state.as_str() == "P1-NEXT" {
            self.game_state = String::from("P2-NEXT");
            return Ok(());
        }

        if self.game_state.as_str() == "P2-NEXT" {
            self.game_state = String::from("P1-NEXT");
            return Ok(());
        }

        Err(ApplyError::InvalidTransaction(String::from(format!(
            "Unhandled state: {}",
            self.game_state
        ))))
    }

    pub fn is_win(&self, letter: &str) -> bool {
        let letter = letter.to_string();
        for (i1, i2, i3) in POSSIBLE_WINS.iter() {
            let board_chars: Vec<char> = self.board.chars().collect();
            if board_chars[*i1 - 1].to_string() == letter
                && board_chars[*i2 - 1].to_string() == letter
                && board_chars[*i3 - 1].to_string() == letter
            {
                return true;
            }
        }
        false
    }

    pub fn display(&self) {
        let b: Vec<char> = self.board.chars().collect();
        info!(
            "
    GAME: {}
    PLAYER 1: {}
    PLAYER 2: {}
    STATE: {}

     {} | {} | {}
    ---|---|---
     {} | {} | {}
    ---|---|---
     {} | {} | {}
    ",
            self.name,
            self.player1,
            self.player2,
            self.game_state,
            b[0],
            b[1],
            b[2],
            b[3],
            b[4],
            b[5],
            b[6],
            b[7],
            b[8]
        );
    }

    pub fn get_state(&self) -> String {
        self.game_state.clone()
    }

    pub fn get_player1(&self) -> String {
        self.player1.clone()
    }

    pub fn get_player2(&self) -> String {
        self.player2.clone()
    }

    pub fn get_board(&self) -> String {
        self.board.clone()
    }

    pub fn set_player1(&mut self, p1: &str) {
        self.player1 = p1.to_string();
        if p1.len() > 6 {
            self.player1_short = p1[..6].to_string();
        } else {
            self.player1_short = String::from(p1);
        }
    }

    pub fn set_player2(&mut self, p2: &str) {
        self.player2 = p2.to_string();
        if p2.len() > 6 {
            self.player2_short = p2[..6].to_string();
        } else {
            self.player2_short = String::from(p2);
        }
    }
}

impl PartialEq for Game {
    fn eq(&self, other: &Self) -> bool {
        self.name == other.name
            && self.game_state == other.board
            && self.game_state == other.game_state
            && self.player1 == other.player1
            && self.player2 == other.player2
    }
}

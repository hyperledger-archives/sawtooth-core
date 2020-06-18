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

use game;
use sawtooth_sdk::messages::processor::TpProcessRequest;
use sawtooth_sdk::processor::handler::{ApplyError, TransactionContext, TransactionHandler};
use serde_json;

pub struct BattleshipTransactionHandler {
    family_name: String,
    family_versions: Vec<String>,
    namespaces: Vec<String>,
}

impl Default for BattleshipTransactionHandler {
    fn default() -> Self {
        Self {
            family_name: "battleship".to_string(),
            family_versions: vec!["1.0".to_string()],
            namespaces: vec![game::get_battleship_prefix().to_string()],
        }
    }
}

impl BattleshipTransactionHandler {
    pub fn new() -> BattleshipTransactionHandler {
        BattleshipTransactionHandler {
            ..Default::default()
        }
    }

    /// Retrieves a single game by name
    fn get_game(
        context: &mut dyn TransactionContext,
        name: &str,
    ) -> Result<Option<game::Game>, ApplyError> {
        let address = game::get_battleship_address(name);
        let state = context.get_state_entry(&address)?;

        match state {
            Some(s) => serde_json::from_slice(s.as_slice()).map_err(|err| {
                ApplyError::InvalidTransaction(format!(
                    "Found existing state that couldn't be deserialized: {} (`{:?}`)",
                    err, s
                ))
            }),
            None => Ok(None),
        }
    }

    /// Stores a single game
    fn store_game(
        context: &mut dyn TransactionContext,
        name: &str,
        game: &game::Game,
    ) -> Result<(), ApplyError> {
        let address = game::get_battleship_address(name);

        let serialized = serde_json::to_string(game).map_err(|err| {
            ApplyError::InvalidTransaction(format!("Couldn't serialize game: {}", err))
        })?;

        context
            .set_state_entry(address, serialized.into())
            .map_err(|err| {
                ApplyError::InvalidTransaction(format!("Couldn't set new game state: {}", err))
            })
    }

    /// Handles CREATE action
    fn handle_create(
        context: &mut dyn TransactionContext,
        name: &str,
        ships: Vec<String>,
    ) -> Result<(), ApplyError> {
        match name.len() {
            1..=255 => {}
            len => Err(ApplyError::InvalidTransaction(format!(
                "Game name must be between 1 - 255 characters, {} is too many",
                len
            )))?,
        }

        if !name.chars().all(char::is_alphanumeric) {
            Err(ApplyError::InvalidTransaction(format!(
                "Game name must only contain characters A-Z, a-z or 0-9, found `{}`.",
                name
            )))?
        }

        if BattleshipTransactionHandler::get_game(context, name)?.is_some() {
            Err(ApplyError::InvalidTransaction(format!(
                "Game `{}` already exists.",
                name
            )))?
        }

        BattleshipTransactionHandler::store_game(
            context,
            name,
            &game::Game {
                ships,
                ..Default::default()
            },
        )
    }

    /// Handles JOIN action
    fn handle_join(
        context: &mut dyn TransactionContext,
        name: &str,
        player: String,
        board: Vec<Vec<String>>,
    ) -> Result<(), ApplyError> {
        let mut game = BattleshipTransactionHandler::get_game(context, name)?
            .ok_or_else(|| ApplyError::InvalidTransaction("Game not found.".into()))?;

        // Should be impossible given the checking we do down below, but here it is for completion
        if game.state != "NEW" {
            Err(ApplyError::InvalidTransaction(String::from("Game is full")))?
        }

        // Check that the board is a valid size
        if board.len() != 10 {
            Err(ApplyError::InvalidTransaction(String::from(
                "Invalid board size",
            )))?
        }

        // Check that each row is of length 10, and that each value in the row is a 128-byte long hash
        for row in &board {
            if row.len() != 10 {
                Err(ApplyError::InvalidTransaction(String::from(
                    "Invalid board size",
                )))?
            }

            for val in row.iter() {
                if val.len() != 128 {
                    Err(ApplyError::InvalidTransaction(String::from(
                        "Invalid board hash",
                    )))?
                }
            }
        }

        match (game.player_1.is_some(), game.player_2.is_some()) {
            // Nobody's joined
            (false, false) => {
                game.player_1 = Some(player);
                game.target_board_1 = board.iter().map(|_| vec!['?'; board.len()]).collect();
                game.hashed_board_1 = board;
            }
            // The first player has joined
            (true, false) => {
                if game.player_1 == Some(player.clone()) {
                    Err(ApplyError::InvalidTransaction(format!(
                        "Player {} is already in the game.",
                        player
                    )))?
                }
                game.player_2 = Some(player);
                game.target_board_2 = board.iter().map(|_| vec!['?'; board.len()]).collect();
                game.hashed_board_2 = board;
                game.state = "P1-NEXT".into();
            }
            // Something weird happened
            (false, true) => Err(ApplyError::InvalidTransaction(
                "Invalid game state, found P2 but no P1!".into(),
            ))?,
            // Go away, we're busy
            (true, true) => Err(ApplyError::InvalidTransaction(String::from("Game is full")))?,
        }

        BattleshipTransactionHandler::store_game(context, name, &game)
    }

    /// Handles FIRE action
    fn handle_fire(
        context: &mut dyn TransactionContext,
        name: &str,
        player: &str,
        column: String,
        row: String,
        reveal_space: Option<char>,
        reveal_nonce: &Option<String>,
    ) -> Result<(), ApplyError> {
        let mut game = BattleshipTransactionHandler::get_game(context, name)?
            .ok_or_else(|| ApplyError::InvalidTransaction("Game not found.".into()))?;

        let current_row = game::parse_row(&row)
            .ok_or_else(|| ApplyError::InvalidTransaction(format!("Invalid row: {}", row)))?;
        let current_col = game::parse_column(&column)
            .ok_or_else(|| ApplyError::InvalidTransaction(format!("Invalid column {}", column)))?;

        // Grab a mutable copy of the board that we'll update and reattach to `game`.
        let mut target_board = match game.state.as_ref() {
            // Everything checks out, return reference to target board
            "P1-NEXT" if game.player_1 == Some(player.to_string()) => game.target_board_2.clone(),
            "P2-NEXT" if game.player_2 == Some(player.to_string()) => game.target_board_1.clone(),

            // It's not their turn, reject the transaction
            "P1-NEXT" | "P2-NEXT" => Err(ApplyError::InvalidTransaction(format!(
                "It is not {}'s turn.",
                player
            )))?,

            // The game is either over or hasn't started, reject the transaction
            "P1-WIN" | "P2-WIN" => Err(ApplyError::InvalidTransaction(String::from(
                "Game complete!",
            )))?,
            "NEW" => Err(ApplyError::InvalidTransaction(String::from(
                "Game doesn't have enough players.",
            )))?,

            // Reject the impossible
            s => Err(ApplyError::InvalidTransaction(format!(
                "Invalid game state: {}",
                s
            )))?,
        };

        if target_board[current_row][current_col] != '?' {
            Err(ApplyError::InvalidTransaction(String::from(
                "Space already fired into.",
            )))?
        }

        // The current player should be revealing whether or not the other player's last
        // fire attempt was successful.
        match (
            &game.last_fire_column,
            &game.last_fire_row,
            reveal_space,
            reveal_nonce,
        ) {
            // Every turn after the first should hit this, unless the client tried giving
            // incomplete information.
            (Some(lfc), Some(lfr), Some(rs), Some(rn)) => {
                let last_row = game::parse_row(&lfr).ok_or_else(|| {
                    ApplyError::InvalidTransaction(format!("Invalid row {}", row))
                })?;

                let last_col = game::parse_column(&lfc).ok_or_else(|| {
                    ApplyError::InvalidTransaction(format!("Invalid column {}", column))
                })?;

                let space_hash = game::get_space_hash(rs, &rn);

                let hashed_board = match game.state.as_ref() {
                    "P1-NEXT" => &game.hashed_board_1,
                    "P2-NEXT" => &game.hashed_board_2,
                    s => Err(ApplyError::InvalidTransaction(format!(
                        "Invalid game state: {}",
                        s
                    )))?,
                };

                if hashed_board[last_row][last_col] != space_hash {
                    Err(ApplyError::InvalidTransaction(format!(
                        "Hash mismatch on reveal: {} != {}",
                        hashed_board[last_row][last_col], space_hash
                    )))?
                }

                match reveal_space {
                    Some('-') => target_board[last_row][last_col] = 'M',
                    Some(_) => target_board[last_row][last_col] = 'H',
                    None => {}
                }
            }

            // This should only happen on the first turn, since there's no previous fire info to send
            (None, None, None, None) => {}

            // All or nothing, reject any attempts to provide partial information
            _ => Err(ApplyError::InvalidTransaction(String::from(
                "Attempted to fire without revealing target",
            )))?,
        }

        let number_of_hits = target_board
            .iter()
            .map(|row| row.iter().filter(|item| **item == 'H').count())
            .sum::<usize>() as u32;

        game.last_fire_column = Some(column);
        game.last_fire_row = Some(row);

        let ships_length: u32 = game.ships.iter().map(|s| s.len() as u32).sum();

        match game.state.as_ref() {
            "P1-NEXT" => game.target_board_2 = target_board,
            "P2-NEXT" => game.target_board_1 = target_board,
            s => Err(ApplyError::InvalidTransaction(format!(
                "Invalid game state: {}",
                s
            )))?,
        }

        game.state = match (game.state.as_ref(), number_of_hits == ships_length) {
            ("P1-NEXT", true) => "P1-WIN".into(),
            ("P1-NEXT", false) => "P2-NEXT".into(),
            ("P2-NEXT", true) => "P2-WIN".into(),
            ("P2-NEXT", false) => "P1-NEXT".into(),
            (s, _) => Err(ApplyError::InvalidTransaction(format!(
                "Invalid state {}",
                s
            )))?,
        };

        BattleshipTransactionHandler::store_game(context, name, &game)
    }
}

impl TransactionHandler for BattleshipTransactionHandler {
    fn family_name(&self) -> String {
        self.family_name.clone()
    }

    fn family_versions(&self) -> Vec<String> {
        self.family_versions.clone()
    }

    fn namespaces(&self) -> Vec<String> {
        self.namespaces.clone()
    }

    fn apply(
        &self,
        request: &TpProcessRequest,
        context: &mut dyn TransactionContext,
    ) -> Result<(), ApplyError> {
        let payload = request.get_payload();
        let action: game::Action = serde_json::from_slice(payload).map_err(|err| {
            ApplyError::InvalidTransaction(format!("Error while parsing action: {}", err))
        })?;

        trace!("Parsed action: `{:?}`.", action);

        let player = request.get_header().get_signer_public_key().into();

        match action {
            game::Action::Create { name, ships } => {
                debug!("Creating game {} with {} ships.", name, ships.len());
                BattleshipTransactionHandler::handle_create(context, &name, ships)
            }
            game::Action::Join { name, board } => {
                debug!("Player {} is joining game {}.", player, name);
                BattleshipTransactionHandler::handle_join(context, &name, player, board)
            }
            game::Action::Fire {
                name,
                column,
                row,
                reveal_space,
                reveal_nonce,
            } => {
                debug!(
                    "Firing on {}{} in game {} for player {}.",
                    row, column, name, player
                );
                BattleshipTransactionHandler::handle_fire(
                    context,
                    &name,
                    &player,
                    column,
                    row,
                    reveal_space,
                    &reveal_nonce,
                )
            }
        }
    }
}

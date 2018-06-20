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

use crypto::digest::Digest;
use crypto::sha2::Sha512;

use sawtooth_sdk::processor::handler::ApplyError;
use sawtooth_sdk::processor::handler::TransactionContext;

use handler::game::Game;

pub fn get_xo_prefix() -> String {
    let mut sha = Sha512::new();
    sha.input_str("xo");
    sha.result_str()[..6].to_string()
}

pub struct XoState<'a> {
    context: &'a mut TransactionContext,
    address_map: HashMap<String, Option<String>>,
}

impl<'a> XoState<'a> {
    pub fn new(context: &'a mut TransactionContext) -> XoState {
        XoState {
            context: context,
            address_map: HashMap::new(),
        }
    }

    fn calculate_address(name: &str) -> String {
        let mut sha = Sha512::new();
        sha.input_str(name);
        get_xo_prefix() + &sha.result_str()[..64].to_string()
    }

    pub fn delete_game(&mut self, game_name: &str) -> Result<(), ApplyError> {
        let mut games = self._load_games(game_name)?;
        games.remove(game_name);
        if games.is_empty() {
            self._delete_game(game_name)?;
        } else {
            self._store_game(game_name, games)?;
        }
        Ok(())
    }

    pub fn set_game(&mut self, game_name: &str, g: Game) -> Result<(), ApplyError> {
        let mut games = self._load_games(game_name)?;
        games.insert(game_name.to_string(), g);
        self._store_game(game_name, games)?;
        Ok(())
    }

    pub fn get_game(&mut self, game_name: &str) -> Result<Option<Game>, ApplyError> {
        let games = self._load_games(game_name)?;
        if games.contains_key(game_name) {
            Ok(Some(games[game_name].clone()))
        } else {
            Ok(None)
        }
    }

    fn _store_game(
        &mut self,
        game_name: &str,
        games: HashMap<String, Game>,
    ) -> Result<(), ApplyError> {
        let address = XoState::calculate_address(game_name);
        let state_string = Game::serialize_games(games);
        self.address_map
            .insert(address.clone(), Some(state_string.clone()));
        let mut sets = HashMap::new();
        sets.insert(address, state_string.into_bytes());
        self.context.set_state(sets)?;
        Ok(())
    }

    fn _delete_game(&mut self, game_name: &str) -> Result<(), ApplyError> {
        let address = XoState::calculate_address(game_name);
        if self.address_map.contains_key(&address) {
            self.address_map.insert(address.clone(), None);
        }
        self.context.delete_state(vec![address])?;
        Ok(())
    }

    fn _load_games(&mut self, game_name: &str) -> Result<HashMap<String, Game>, ApplyError> {
        let address = XoState::calculate_address(game_name);
        let mut games = HashMap::new();

        if self.address_map.contains_key(&address) {
            if let Some(ref serialized_games) = self.address_map[&address] {
                let t = Game::deserialize_games((*serialized_games).clone());
                match t {
                    Some(g) => games = g,
                    None => {
                        return Err(ApplyError::InvalidTransaction(String::from(
                            "Invalid serialization of game state",
                        )))
                    }
                }
            }
        } else {
            if let Some(state_bytes) = self.context.get_state(vec![address.to_string()])? {
                let state_string = match ::std::str::from_utf8(&state_bytes) {
                    Ok(s) => s,
                    Err(_) => {
                        return Err(ApplyError::InvalidTransaction(String::from(
                            "Invalid serialization of game state",
                        )))
                    }
                };
                self.address_map
                    .insert(address, Some(state_string.to_string()));
                let t = Game::deserialize_games(state_string.to_string());
                match t {
                    Some(g) => games = g,
                    None => {
                        return Err(ApplyError::InvalidTransaction(String::from(
                            "Invalid serialization of game state",
                        )))
                    }
                }
            } else {
                self.address_map.insert(address, None);
            }
        }
        Ok(games)
    }
}

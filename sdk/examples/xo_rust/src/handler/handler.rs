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

use sawtooth_sdk::messages::processor::TpProcessRequest;
use sawtooth_sdk::processor::handler::ApplyError;
use sawtooth_sdk::processor::handler::TransactionContext;
use sawtooth_sdk::processor::handler::TransactionHandler;

use handler::game::Game;
use handler::payload::XoPayload;
use handler::state::get_xo_prefix;
use handler::state::XoState;

pub struct XoTransactionHandler {
    family_name: String,
    family_versions: Vec<String>,
    namespaces: Vec<String>,
}

impl XoTransactionHandler {
    pub fn new() -> XoTransactionHandler {
        XoTransactionHandler {
            family_name: String::from("xo"),
            family_versions: vec![String::from("1.0")],
            namespaces: vec![String::from(get_xo_prefix().to_string())],
        }
    }
}

impl TransactionHandler for XoTransactionHandler {
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
        context: &mut TransactionContext,
    ) -> Result<(), ApplyError> {
        let header = &request.header;
        let signer = match &header.as_ref() {
            Some(s) => &s.signer_public_key,
            None => {
                return Err(ApplyError::InvalidTransaction(String::from(
                    "Invalid header",
                )))
            }
        };

        let payload = XoPayload::new(&request.payload)?;

        let mut state = XoState::new(context);

        info!(
            "Payload: {} {} {}",
            payload.get_name(),
            payload.get_action(),
            payload.get_space(),
        );

        let game = state.get_game(payload.get_name().as_str())?;

        match payload.get_action().as_str() {
            "delete" => {
                if game.is_none() {
                    return Err(ApplyError::InvalidTransaction(String::from(
                        "Invalid action: game does not exist",
                    )));
                }
                state.delete_game(payload.get_name().as_str())?;
            }
            "create" => {
                if game.is_none() {
                    let game = Game::new(payload.get_name());
                    state.set_game(payload.get_name().as_str(), game)?;
                    info!("Created game: {}", payload.get_name().as_str());
                } else {
                    return Err(ApplyError::InvalidTransaction(String::from(
                        "Invalid action: Game already exists",
                    )));
                }
            }
            "take" => {
                if let Some(mut g) = game {
                    match g.get_state().as_str() {
                        "P1-WIN" | "P2-WIN" | "TIE" => {
                            return Err(ApplyError::InvalidTransaction(String::from(
                                "Invalid action: Game has ended",
                            )))
                        }
                        "P1-NEXT" => {
                            let p1 = g.get_player1();
                            if !p1.is_empty() && p1.as_str() != signer {
                                return Err(ApplyError::InvalidTransaction(String::from(
                                    "Not player 2's turn",
                                )));
                            }
                        }
                        "P2-NEXT" => {
                            let p2 = g.get_player2();
                            if !p2.is_empty() && p2.as_str() != signer {
                                return Err(ApplyError::InvalidTransaction(String::from(
                                    "Not player 1's turn",
                                )));
                            }
                        }
                        _ => {
                            return Err(ApplyError::InvalidTransaction(String::from(
                                "Invalid state",
                            )))
                        }
                    }

                    let board_chars: Vec<char> = g.get_board().chars().collect();
                    if board_chars[payload.get_space() - 1] != '-' {
                        return Err(ApplyError::InvalidTransaction(String::from(
                            format!("Space {} is already taken", payload.get_space()).as_str(),
                        )));
                    }

                    if g.get_player1().is_empty() {
                        g.set_player1(signer);
                    } else if g.get_player2().is_empty() {
                        g.set_player2(signer)
                    }

                    g.mark_space(payload.get_space())?;
                    g.update_state()?;

                    g.display();

                    state.set_game(payload.get_name().as_str(), g)?;
                } else {
                    return Err(ApplyError::InvalidTransaction(String::from(
                        "Invalid action: Take requires an existing game",
                    )));
                }
            }
            other_action => {
                return Err(ApplyError::InvalidTransaction(String::from(format!(
                    "Invalid action: '{}'",
                    other_action
                ))));
            }
        }

        Ok(())
    }
}

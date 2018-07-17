use std::collections::HashMap;

use crypto::digest::Digest;
use crypto::sha2::Sha512;
use serde_json;

use sawtooth_sdk::messages::processor::TpProcessRequest;
use sawtooth_sdk::processor::handler::{ApplyError, TransactionContext, TransactionHandler};

#[derive(Serialize, Deserialize, Debug, Clone)]
struct Game {
    #[serde(rename = "State")]
    state: String,
    #[serde(rename = "Ships")]
    ships: Vec<String>,
    #[serde(rename = "Player1")]
    player_1: Option<String>,
    #[serde(rename = "HashedBoard1")]
    hashed_board_1: Vec<Vec<String>>,
    #[serde(rename = "TargetBoard1")]
    target_board_1: Vec<Vec<char>>,
    #[serde(rename = "Player2")]
    player_2: Option<String>,
    #[serde(rename = "HashedBoard2")]
    hashed_board_2: Vec<Vec<String>>,
    #[serde(rename = "TargetBoard2")]
    target_board_2: Vec<Vec<char>>,
    #[serde(rename = "LastFireColumn")]
    last_fire_column: Option<String>,
    #[serde(rename = "LastFireRow")]
    last_fire_row: Option<String>,
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

#[derive(Serialize, Deserialize, Debug)]
#[serde(tag = "Action")]
enum Action {
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

pub struct BattleshipTransactionHandler {
    family_name: String,
    family_versions: Vec<String>,
    namespaces: Vec<String>,
}

impl BattleshipTransactionHandler {
    pub fn new() -> BattleshipTransactionHandler {
        BattleshipTransactionHandler {
            family_name: "battleship".to_string(),
            family_versions: vec!["1.0".to_string()],
            namespaces: vec![get_battleship_prefix().to_string()],
        }
    }

    /// Gets overall state for all Battleship games
    fn get_state(context: &mut TransactionContext, name: &str) -> Result<HashMap<String, Game>, ApplyError> {
        let address = get_battleship_address(name);
        let state = context.get_state(vec![address])?;

        match state {
            Some(s) => serde_json::from_slice(s.as_slice()).map_err(|err| {
                ApplyError::InvalidTransaction(format!("Found existing state that couldn't be deserialized: {}", err))
            }),
            None => Ok(HashMap::new()),
        }
    }

    /// Retrieves a single game by name
    fn get_game(context: &mut TransactionContext, name: &str) -> Result<Game, ApplyError> {
        let mut state = BattleshipTransactionHandler::get_state(context, name)?;
        state
            .remove(name)
            .ok_or_else(|| ApplyError::InvalidTransaction("Game not found.".into()))
    }

    /// Stores a single game
    fn store_game(context: &mut TransactionContext, name: &str, game: Game) -> Result<(), ApplyError> {
        let address = get_battleship_address(name);

        let mut game_map: HashMap<String, Game> = BattleshipTransactionHandler::get_state(context, name)?;

        game_map.insert(name.into(), game);

        let serialized = serde_json::to_string(&game_map)
            .map_err(|err| ApplyError::InvalidTransaction(format!("Couldn't serialize game: {}", err)))?;

        let mut state_map = HashMap::new();
        state_map.insert(address, serialized.into());

        context
            .set_state(state_map)
            .map_err(|err| ApplyError::InvalidTransaction(format!("Couldn't set new game state: {}", err)))
    }

    /// Handles CREATE action
    fn handle_create(context: &mut TransactionContext, name: &str, ships: Vec<String>) -> Result<(), ApplyError> {
        if !name.chars().all(char::is_alphanumeric) {
            Err(ApplyError::InvalidTransaction(format!(
                "Game name must only contain characters A-Z, a-z or 0-9, found `{}`.",
                name
            )))?
        }

        if BattleshipTransactionHandler::get_game(context, name).is_ok() {
            Err(ApplyError::InvalidTransaction(format!(
                "Game `{}` already exists.",
                name
            )))?
        }

        BattleshipTransactionHandler::store_game(
            context,
            name,
            Game {
                ships,
                ..Default::default()
            },
        )
    }

    /// Handles JOIN action
    fn handle_join(
        context: &mut TransactionContext,
        name: &str,
        player: String,
        board: Vec<Vec<String>>,
    ) -> Result<(), ApplyError> {
        let mut game = BattleshipTransactionHandler::get_game(context, name)?;

        // Should be impossible given the checking we do down below, but here it is for completion
        if game.state != "NEW" {
            Err(ApplyError::InvalidTransaction(String::from("Game is full")))?
        }

        // Check that the board is a valid size
        if board.len() != 10 {
            Err(ApplyError::InvalidTransaction(String::from("Invalid board size")))?
        }

        // Check that each row is of length 10, and that each value in the row is a 128-byte long hash
        for row in &board {
            if row.len() != 10 {
                Err(ApplyError::InvalidTransaction(String::from("Invalid board size")))?
            }

            for val in row.iter() {
                if val.len() != 128 {
                    Err(ApplyError::InvalidTransaction(String::from("Invalid board hash")))?
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

        BattleshipTransactionHandler::store_game(context, name, game)
    }

    /// Handles FIRE action
    fn handle_fire(
        context: &mut TransactionContext,
        name: &str,
        player: &str,
        column: String,
        row: String,
        reveal_space: Option<char>,
        reveal_nonce: &Option<String>,
    ) -> Result<(), ApplyError> {
        let mut game = BattleshipTransactionHandler::get_game(context, name)?;

        let current_row =
            parse_row(&row).ok_or_else(|| ApplyError::InvalidTransaction(format!("Invalid row: {}", row)))?;
        let current_col =
            parse_column(&column).ok_or_else(|| ApplyError::InvalidTransaction(format!("Invalid column {}", column)))?;

        // Grab a mutable copy of the board that we'll update and reattach to `game`.
        let mut target_board = match game.state.as_ref() {
            // Everything checks out, return reference to target board
            "P1-NEXT" if game.player_1 == Some(player.to_string()) => game.target_board_1.clone(),
            "P2-NEXT" if game.player_2 == Some(player.to_string()) => game.target_board_2.clone(),

            // It's not their turn, reject the transaction
            "P1-NEXT" | "P2-NEXT" => Err(ApplyError::InvalidTransaction(format!("It is not {}'s turn.", player)))?,

            // The game is either over or hasn't started, reject the transaction
            "P1-WIN" | "P2-WIN" => Err(ApplyError::InvalidTransaction(String::from("Game complete!")))?,
            "NEW" => Err(ApplyError::InvalidTransaction(String::from(
                "Game doesn't have enough players.",
            )))?,

            // Reject the impossible
            s => Err(ApplyError::InvalidTransaction(format!("Invalid game state: {}", s)))?,
        };

        if target_board[current_row][current_col] != '?' {
            Err(ApplyError::InvalidTransaction(String::from(
                "Space already fired into.",
            )))?
        }

        // The current player should be revealing whether or not the other player's last
        // fire attempt was successful.
        match (&game.last_fire_column, &game.last_fire_row, reveal_space, reveal_nonce) {
            // Every turn after the first should hit this, unless the client tried giving
            // incomplete information.
            (Some(lfc), Some(lfr), Some(rs), Some(rn)) => {
                let last_row =
                    parse_row(&lfr).ok_or_else(|| ApplyError::InvalidTransaction(format!("Invalid row {}", row)))?;

                let last_col = parse_column(&lfc)
                    .ok_or_else(|| ApplyError::InvalidTransaction(format!("Invalid column {}", column)))?;

                let space_hash = get_space_hash(rs, &rn);

                let hashed_board = match game.state.as_ref() {
                    "P1-NEXT" => &game.hashed_board_1,
                    "P2-NEXT" => &game.hashed_board_2,
                    s => Err(ApplyError::InvalidTransaction(format!("Invalid game state: {}", s)))?,
                };

                if hashed_board[last_row][last_col] != space_hash {
                    Err(ApplyError::InvalidTransaction(format!(
                        "Hash mismatch on reveal: {} != {}",
                        hashed_board[last_row][last_col], space_hash
                    )))?
                }

                match reveal_space {
                    Some('_') => target_board[last_row][last_col] = 'M',
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
            "P1-NEXT" => game.target_board_1 = target_board,
            "P2-NEXT" => game.target_board_1 = target_board,
            s => Err(ApplyError::InvalidTransaction(format!("Invalid game state: {}", s)))?,
        }

        game.state = match (game.state.as_ref(), number_of_hits == ships_length) {
            ("P1-NEXT", true) => "P1-WIN".into(),
            ("P1-NEXT", false) => "P2-NEXT".into(),
            ("P2-NEXT", true) => "P2-WIN".into(),
            ("P2-NEXT", false) => "P1-NEXT".into(),
            (s, _) => Err(ApplyError::InvalidTransaction(format!("Invalid state {}", s)))?,
        };

        BattleshipTransactionHandler::store_game(context, name, game)
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

    fn apply(&self, request: &TpProcessRequest, context: &mut TransactionContext) -> Result<(), ApplyError> {
        let payload = request.get_payload();

        let action: Action = serde_json::from_slice(payload)
            .map_err(|err| ApplyError::InvalidTransaction(format!("Error while parsing action: {}", err)))?;

        let player = request.get_header().get_signer_public_key().into();

        match action {
            Action::Create { name, ships } => BattleshipTransactionHandler::handle_create(context, &name, ships),
            Action::Join { name, board } => BattleshipTransactionHandler::handle_join(context, &name, player, board),
            Action::Fire {
                name,
                column,
                row,
                reveal_space,
                reveal_nonce,
            } => BattleshipTransactionHandler::handle_fire(
                context,
                &name,
                &player,
                column,
                row,
                reveal_space,
                &reveal_nonce,
            ),
        }
    }
}

/// Convenience function for calculating prefix for the `battleship` transaction family
fn get_battleship_prefix() -> String {
    let mut sha = Sha512::new();
    sha.input_str("battleship");
    sha.result_str()[..6].to_string()
}

/// Hash the name of a game of battleship
/// Used for calculating the state address that state for a given game is stored at
fn get_battleship_name_hash(name: &str) -> String {
    let mut sha = Sha512::new();
    sha.input_str(name);
    sha.result_str()[..64].to_string()
}

/// Get a state address for a given game of battleship
fn get_battleship_address(name: &str) -> String {
    vec![get_battleship_prefix(), get_battleship_name_hash(name)].join("")
}

/// Hash the value and nonce for a revealed space
/// When a player joins, we're given a hashed board of their ship locations.
/// On each player's turn, they give us a nonce and the value of that space,
/// e.g. `'-'` and `"g54h45hwer"`. We hash those together and compare against
/// the given hashed board to ensure that the player didn't lie about where
/// their ships were located.
fn get_space_hash(space: char, nonce: &str) -> String {
    let mut sha = Sha512::new();
    sha.input_str(nonce);
    sha.input_str(&space.to_string());
    sha.result_str()
}

/// Parses a column value such as "B" to be a numerical column value.
/// Drops characters other than the first while parsing, and returns
/// `None` if parsed number isn't in `[0, 10)`.
fn parse_column(col: &str) -> Option<usize> {
    match col.chars().next()? as usize - 'A' as usize {
        num @ 0...9 => Some(num),
        _ => None,
    }
}

/// Parses a row value such as "1" to be a numerical row value
/// Returns `None` if parsed number isn't in `[0, 10)`.
fn parse_row(row: &str) -> Option<usize> {
    match row.parse::<usize>().ok()? - 1 {
        num @ 0...9 => Some(num),
        _ => None,
    }
}

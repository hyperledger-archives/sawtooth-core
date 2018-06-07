use std::env;
use std::io::prelude::*;
use std::fs::File;

use users::get_current_username;

use sawtooth_sdk::signing::secp256k1::Secp256k1PrivateKey;

use errors::IntkeyError;

pub fn load_signing_key(_name: Option<&str>) -> Result<Secp256k1PrivateKey, IntkeyError> {
    let username: String = _name.map(|s| String::from(s))
                           .ok_or_else(|| env::var("USER"))
                           .or_else(|_| get_current_username().ok_or(0))
                           .map_err(|_| {
                               IntkeyError::UsernameError
                           })?;

    let private_key_filename = env::home_dir()
        .ok_or(IntkeyError::UsernameError) 
        .and_then(|mut p| {                
            p.push(".sawtooth");
            p.push("keys");
            p.push(format!("{}.priv", &username));
            Ok(p)
        })?;

    if !private_key_filename.as_path().exists() {
        return Err(IntkeyError::KeyfileError)
    }

    let mut f = File::open(&private_key_filename)?;

    let mut contents = String::new();
    f.read_to_string(&mut contents)?;

    let key_str = match contents.lines().next() {
        Some(k) => k,
        None => return Err(IntkeyError::EmptyKeyfileError)
    };

    Ok(Secp256k1PrivateKey::from_hex(&key_str)?)

}


/*
 * Copyright 2017 Intel Corporation
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
use crypto::digest::Digest;
use crypto::sha2::Sha256;

use rand::os::OsRng;
use rand::Rng;
use secp256k1;

use signing::Context;
use signing::Error;
use signing::PrivateKey;
use signing::PublicKey;

impl From<secp256k1::Error> for Error {
    fn from(e: secp256k1::Error) -> Self {
        Error::SigningError(Box::new(e))
    }
}

pub struct Secp256k1PrivateKey {
    private: Vec<u8>,
}

impl Secp256k1PrivateKey {
    pub fn from_hex(s: &str) -> Result<Self, Error> {
        hex_str_to_bytes(s).map(|key_bytes| Secp256k1PrivateKey { private: key_bytes })
    }
}

impl PrivateKey for Secp256k1PrivateKey {
    fn get_algorithm_name(&self) -> &str {
        "secp256k1"
    }

    fn as_hex(&self) -> String {
        bytes_to_hex_str(&self.private)
    }

    fn as_slice(&self) -> &[u8] {
        &self.private
    }
}

pub struct Secp256k1PublicKey {
    public: Vec<u8>,
}

impl Secp256k1PublicKey {
    pub fn from_hex(s: &str) -> Result<Self, Error> {
        hex_str_to_bytes(s).map(|key_bytes| Secp256k1PublicKey { public: key_bytes })
    }
}

impl PublicKey for Secp256k1PublicKey {
    fn get_algorithm_name(&self) -> &str {
        "secp256k1"
    }

    fn as_hex(&self) -> String {
        bytes_to_hex_str(&self.public)
    }

    fn as_slice(&self) -> &[u8] {
        &self.public
    }
}

pub struct Secp256k1Context {
    context: secp256k1::Secp256k1,
}

impl Secp256k1Context {
    pub fn new() -> Self {
        Secp256k1Context {
            context: secp256k1::Secp256k1::new(),
        }
    }
}

impl Default for Secp256k1Context {
    fn default() -> Self {
        Self::new()
    }
}

impl Context for Secp256k1Context {
    fn get_algorithm_name(&self) -> &str {
        "secp256k1"
    }

    fn sign(&self, message: &[u8], key: &PrivateKey) -> Result<String, Error> {
        let mut sha = Sha256::new();
        sha.input(message);
        let hash: &mut [u8] = &mut [0; 32];
        sha.result(hash);

        let sk = secp256k1::key::SecretKey::from_slice(&self.context, key.as_slice())?;
        let sig = self
            .context
            .sign(&secp256k1::Message::from_slice(hash)?, &sk)?;
        let compact = sig.serialize_compact(&self.context);
        Ok(compact
            .iter()
            .map(|b| format!("{:02x}", b))
            .collect::<Vec<_>>()
            .join(""))
    }

    fn verify(&self, signature: &str, message: &[u8], key: &PublicKey) -> Result<bool, Error> {
        let mut sha = Sha256::new();
        sha.input(message);
        let hash: &mut [u8] = &mut [0; 32];
        sha.result(hash);

        let result = self.context.verify(
            &secp256k1::Message::from_slice(hash)?,
            &secp256k1::Signature::from_compact(&self.context, &hex_str_to_bytes(&signature)?)?,
            &secp256k1::key::PublicKey::from_slice(&self.context, key.as_slice())?,
        );
        match result {
            Ok(()) => Ok(true),
            Err(secp256k1::Error::IncorrectSignature) => Ok(false),
            Err(err) => Err(Error::from(err)),
        }
    }

    fn get_public_key(&self, private_key: &PrivateKey) -> Result<Box<PublicKey>, Error> {
        let sk = secp256k1::key::SecretKey::from_slice(&self.context, private_key.as_slice())?;
        let result = Secp256k1PublicKey::from_hex(
            bytes_to_hex_str(
                &secp256k1::key::PublicKey::from_secret_key(&self.context, &sk)?
                    .serialize_vec(&self.context, true),
            ).as_str(),
        );
        match result {
            Err(err) => Err(err),
            Ok(pk) => Ok(Box::new(pk)),
        }
    }

    fn new_random_private_key(&self) -> Result<Box<PrivateKey>, Error> {
        let mut rng = OsRng::new().map_err(|err| Error::KeyGenError(format!("{}", err)))?;
        let mut key = [0u8; secp256k1::constants::SECRET_KEY_SIZE];
        rng.fill_bytes(&mut key);
        Ok(Box::new(Secp256k1PrivateKey {
            private: Vec::from(&key[..]),
        }))
    }
}

fn hex_str_to_bytes(s: &str) -> Result<Vec<u8>, Error> {
    for (i, ch) in s.chars().enumerate() {
        if !ch.is_digit(16) {
            return Err(Error::ParseError(format!(
                "invalid character position {}",
                i
            )));
        }
    }

    let input: Vec<_> = s.chars().collect();

    let decoded: Vec<u8> = input
        .chunks(2)
        .map(|chunk| {
            ((chunk[0].to_digit(16).unwrap() << 4) | (chunk[1].to_digit(16).unwrap())) as u8
        }).collect();

    Ok(decoded)
}

fn bytes_to_hex_str(b: &[u8]) -> String {
    b.iter()
        .map(|b| format!("{:02x}", b))
        .collect::<Vec<_>>()
        .join("")
}

#[cfg(test)]
mod secp256k1_test {
    use super::super::create_context;
    use super::super::CryptoFactory;
    use super::super::PrivateKey;
    use super::super::PublicKey;
    use super::Secp256k1PrivateKey;
    use super::Secp256k1PublicKey;

    static KEY1_PRIV_HEX: &'static str =
        "2f1e7b7a130d7ba9da0068b3bb0ba1d79e7e77110302c9f746c3c2a63fe40088";
    static KEY1_PUB_HEX: &'static str =
        "026a2c795a9776f75464aa3bda3534c3154a6e91b357b1181d3f515110f84b67c5";

    static KEY2_PRIV_HEX: &'static str =
        "51b845c2cdde22fe646148f0b51eaf5feec8c82ee921d5e0cbe7619f3bb9c62d";
    static KEY2_PUB_HEX: &'static str =
        "039c20a66b4ec7995391dbec1d8bb0e2c6e6fd63cd259ed5b877cb4ea98858cf6d";

    static MSG1: &'static str = "test";
    static MSG1_KEY1_SIG: &'static str = "5195115d9be2547b720ee74c23dd841842875db6eae1f5da8605b050a49e702b4aa83be72ab7e3cb20f17c657011b49f4c8632be2745ba4de79e6aa05da57b35";

    static MSG2: &'static str = "test2";
    static MSG2_KEY2_SIG: &'static str = "d589c7b1fa5f8a4c5a389de80ae9582c2f7f2a5e21bab5450b670214e5b1c1235e9eb8102fd0ca690a8b42e2c406a682bd57f6daf6e142e5fa4b2c26ef40a490";

    #[test]
    fn hex_key() {
        let priv_key = Secp256k1PrivateKey::from_hex(KEY1_PRIV_HEX).unwrap();
        assert_eq!(priv_key.get_algorithm_name(), "secp256k1");
        assert_eq!(priv_key.as_hex(), KEY1_PRIV_HEX);

        let pub_key = Secp256k1PublicKey::from_hex(KEY1_PUB_HEX).unwrap();
        assert_eq!(pub_key.get_algorithm_name(), "secp256k1");
        assert_eq!(pub_key.as_hex(), KEY1_PUB_HEX);
    }

    #[test]
    fn priv_to_public_key() {
        let context = create_context("secp256k1").unwrap();
        assert_eq!(context.get_algorithm_name(), "secp256k1");

        let priv_key1 = Secp256k1PrivateKey::from_hex(KEY1_PRIV_HEX).unwrap();
        assert_eq!(priv_key1.get_algorithm_name(), "secp256k1");
        assert_eq!(priv_key1.as_hex(), KEY1_PRIV_HEX);

        let public_key1 = context.get_public_key(&priv_key1).unwrap();
        assert_eq!(public_key1.as_hex(), KEY1_PUB_HEX);

        let priv_key2 = Secp256k1PrivateKey::from_hex(KEY2_PRIV_HEX).unwrap();
        assert_eq!(priv_key2.get_algorithm_name(), "secp256k1");
        assert_eq!(priv_key2.as_hex(), KEY2_PRIV_HEX);

        let public_key2 = context.get_public_key(&priv_key2).unwrap();
        assert_eq!(public_key2.as_hex(), KEY2_PUB_HEX);
    }

    #[test]
    fn check_invalid_digit() {
        let mut priv_chars: Vec<char> = KEY1_PRIV_HEX.chars().collect();
        priv_chars[3] = 'i';
        let priv_result =
            Secp256k1PrivateKey::from_hex(priv_chars.into_iter().collect::<String>().as_str());
        assert!(priv_result.is_err());

        let mut pub_chars: Vec<char> = KEY1_PUB_HEX.chars().collect();
        pub_chars[3] = 'i';
        let result =
            Secp256k1PublicKey::from_hex(pub_chars.into_iter().collect::<String>().as_str());
        assert!(result.is_err());
    }

    #[test]
    fn single_key_signing() {
        let context = create_context("secp256k1").unwrap();
        assert_eq!(context.get_algorithm_name(), "secp256k1");

        let factory = CryptoFactory::new(&*context);
        assert_eq!(factory.get_context().get_algorithm_name(), "secp256k1");

        let priv_key = Secp256k1PrivateKey::from_hex(KEY1_PRIV_HEX).unwrap();
        assert_eq!(priv_key.get_algorithm_name(), "secp256k1");
        assert_eq!(priv_key.as_hex(), KEY1_PRIV_HEX);

        let signer = factory.new_signer(&priv_key);
        let signature = signer.sign(&String::from(MSG1).into_bytes()).unwrap();
        assert_eq!(signature, MSG1_KEY1_SIG);
    }

    #[test]
    fn many_key_signing() {
        let context = create_context("secp256k1").unwrap();
        assert_eq!(context.get_algorithm_name(), "secp256k1");

        let priv_key1 = Secp256k1PrivateKey::from_hex(KEY1_PRIV_HEX).unwrap();
        assert_eq!(priv_key1.get_algorithm_name(), "secp256k1");
        assert_eq!(priv_key1.as_hex(), KEY1_PRIV_HEX);

        let priv_key2 = Secp256k1PrivateKey::from_hex(KEY2_PRIV_HEX).unwrap();
        assert_eq!(priv_key2.get_algorithm_name(), "secp256k1");
        assert_eq!(priv_key2.as_hex(), KEY2_PRIV_HEX);

        let signature = context
            .sign(&String::from(MSG1).into_bytes(), &priv_key1)
            .unwrap();
        assert_eq!(signature, MSG1_KEY1_SIG);

        let signature = context
            .sign(&String::from(MSG2).into_bytes(), &priv_key2)
            .unwrap();
        assert_eq!(signature, MSG2_KEY2_SIG);
    }

    #[test]
    fn verification() {
        let context = create_context("secp256k1").unwrap();
        assert_eq!(context.get_algorithm_name(), "secp256k1");

        let pub_key1 = Secp256k1PublicKey::from_hex(KEY1_PUB_HEX).unwrap();
        assert_eq!(pub_key1.get_algorithm_name(), "secp256k1");
        assert_eq!(pub_key1.as_hex(), KEY1_PUB_HEX);

        let result = context.verify(MSG1_KEY1_SIG, &String::from(MSG1).into_bytes(), &pub_key1);
        assert_eq!(result.unwrap(), true);
    }

    #[test]
    fn verification_error() {
        let context = create_context("secp256k1").unwrap();
        assert_eq!(context.get_algorithm_name(), "secp256k1");

        let pub_key1 = Secp256k1PublicKey::from_hex(KEY1_PUB_HEX).unwrap();
        assert_eq!(pub_key1.get_algorithm_name(), "secp256k1");
        assert_eq!(pub_key1.as_hex(), KEY1_PUB_HEX);

        // This signature doesn't match for MSG1/KEY1
        let result = context.verify(MSG2_KEY2_SIG, &String::from(MSG1).into_bytes(), &pub_key1);
        assert_eq!(result.unwrap(), false);
    }
}

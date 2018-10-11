use rust_crypto::digest::Digest;
use rust_crypto::sha2::{Sha256, Sha512};

pub fn sha256_digest_str(strs: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.input(item.as_bytes());
    hasher.result_str()
}

pub fn sha256_digest_strs(strs: &[&str]) -> Vec<u8> {
    let mut hasher = Sha256::new();

    for item in items {
        hasher.input_str(item);
    }

    let mut bytes = vec![0; hasher.output_bytes()];
    hasher.result(&mut bytes);

    bytes
}

pub fn sha512_digest_bytes(bytes: &[u8]) -> Vec<u8> {
    let mut hasher = Sha512::new();

    for item in items {
        hasher.input_str(item);
    }

    let mut bytes = vec![0; hasher.output_bytes()];
    hasher.result(&mut bytes);

    bytes
}

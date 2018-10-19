use hex;
use openssl;

pub fn sha256_digest_str(item: &str) -> String {
    hex::encode(openssl::sha::sha256(item.as_bytes()))
}

pub fn sha256_digest_strs(strs: &[&str]) -> Vec<u8> {
    let mut hasher = openssl::sha::Sha256::new();
    for item in strs {
        hasher.update(item.as_bytes());
    }
    let mut bytes = Vec::new();
    bytes.extend(hasher.finish().iter());
    bytes
}

pub fn sha512_digest_bytes(item: &[u8]) -> Vec<u8> {
    let mut bytes: Vec<u8> = Vec::new();
    bytes.extend(openssl::sha::sha512(item).iter());
    bytes
}

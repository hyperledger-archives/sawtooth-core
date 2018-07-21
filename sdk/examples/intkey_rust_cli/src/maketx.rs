use crypto::digest::Digest;
use crypto::sha2::Sha512;

use sawtooth_sdk::signing;

use makebatch::{ create_batch, create_batch_list_from_one, create_transaction };
use keymgmt::load_signing_key;
use submitbatch::submit_batch_list;
use errors::IntkeyError;



const INTKEY_PREFIX: &'static str = "1cf126";
const MAX_VALUE: u64 = 4_294_967_295;
const MAX_NAME_LEN: usize = 20;

// Do not change IntkeyPayload attribute names to lowercase. They will no
// longer be accepted by the transaction processor.
#[allow(non_snake_case)]
#[derive(Serialize, Deserialize, Debug, PartialEq)]
pub struct IntkeyPayload {
    Verb: String,
    Name: String,
    Value: u64
}



impl IntkeyPayload {
    pub fn new(_verb: &str, _name: &str, _value: &str) -> Result<Self, IntkeyError> {
        let parsed_val = _value.parse::<u64>()?;
        let string_name = String::from(_name);

        if parsed_val > MAX_VALUE {
            Err(IntkeyError::ValueOverflow)
        } else if string_name.len() > MAX_NAME_LEN {
            Err(IntkeyError::NameOverflow { key_length: string_name.len() })
        } else if string_name.is_ascii() == false {
            Err(IntkeyError::NonAsciiNameError)
        } else if _verb != "set" && _verb != "inc" && _verb != "dec"{
            Err(IntkeyError::BadVerb { received_verb: String::from(_verb) })
        } else {
            Ok(IntkeyPayload { Verb: String::from(_verb), Name: string_name, Value: parsed_val })
        }
    }

    pub fn get_storage_addr(&self) -> String {
        let mut sha = Sha512::new();
        let name_bytes = self.Name.as_bytes();
        sha.input(name_bytes);
        let result_string = sha.result_str();
        let hashed_name_bytes = result_string.as_bytes();
        let as_string = String::from_utf8_lossy(&hashed_name_bytes[64..]).into_owned();
        format!("{}{}", INTKEY_PREFIX, as_string)
    }
}



pub fn build_and_exec(_verb: &str, _name: &str, _value: &str, _keyfile: Option<&str>, _url: Option<&str>) -> Result<(), IntkeyError> {
    let payload = IntkeyPayload::new(_verb, _name, _value)?;

    let private_key = load_signing_key(_keyfile)?;
    let context = signing::create_context("secp256k1")?;
    let public_key = context.get_public_key(&private_key)?.as_hex();
    let factory = signing::CryptoFactory::new(&*context);
    let signer = factory.new_signer(&private_key);

    let txn = create_transaction(payload, &signer, &public_key)?;
    let batch = create_batch(txn, &signer, &public_key)?;
    let batch_list = create_batch_list_from_one(batch);

    submit_batch_list(_url, &batch_list)?;

    Ok(())
}




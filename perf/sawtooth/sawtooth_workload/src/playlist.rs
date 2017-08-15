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

//! Tools for generating YAML playlists of transactions.

extern crate yaml_rust;
extern crate rand;

use std::error;
use std::io::Write;
use std::io::Error as StdIoError;
use std::fmt;

use self::yaml_rust::YamlEmitter;
use self::yaml_rust::Yaml;
use self::yaml_rust::EmitError;
use self::yaml_rust::yaml::Hash;
use self::rand::Rng;
use self::rand::StdRng;
use self::rand::SeedableRng;

use smallbank;
use smallbank::SmallbankTransactionPayload;
use smallbank::SmallbankTransactionPayload_PayloadType as SBPayloadType;

macro_rules! yaml_map(
    { $($key:expr => $value:expr),+ } => {
        {
            let mut m = Hash::new();
            $(m.insert(Yaml::from_str($key), $value);)+
            Yaml::Hash(m)
        }
    };
);
pub fn generate_smallbank_playlist<'a>(output: &'a mut Write,
                                       num_accounts: usize,
                                       num_transactions: usize,
                                       seed: Option<i32>)
    -> Result<(), PlaylistError>
{
    let mut fmt_writer = FmtWriter::new(output);
    let mut emitter = YamlEmitter::new(&mut fmt_writer);

    let txn_array: Vec<Yaml> = create_smallbank_playlist(num_accounts, num_transactions, seed)
        .map(Yaml::from)
        .collect();

    let final_yanl = Yaml::Array(txn_array);
    try!(emitter.dump(&final_yanl).map_err(PlaylistError::YamlOutputError));

    Ok(())
}


pub fn create_smallbank_playlist(num_accounts: usize,
                                 num_transactions: usize,
                                 seed: Option<i32>)
    -> SmallbankIter
{
    let rng = match seed {
        Some(seed) => {
            let v = vec![seed as usize];
            let seed: &[usize] =  &v;
            SeedableRng::from_seed(seed)
        },
        None => StdRng::new().unwrap()
    };
    SmallbankIter {
        num_accounts: num_accounts,
        current_account: 0,
        num_transactions: num_transactions,
        current_transaction: 0,
        rng: rng
    }
}

pub struct SmallbankIter {
    num_accounts: usize,
    current_account: usize,
    num_transactions: usize,
    current_transaction: usize,
    rng: StdRng,
}

impl Iterator for SmallbankIter {
    type Item = SmallbankTransactionPayload;

    fn next(&mut self) -> Option<Self::Item> {
        if self.current_account < self.num_accounts {
            let mut payload =  SmallbankTransactionPayload::new();

            let mut create_account = smallbank::SmallbankTransactionPayload_CreateAccountTransactionData::new();
            create_account.set_customer_id(self.current_account as u32);
            create_account.set_customer_name(format!("customer_{:06}", self.current_account));

            create_account.set_initial_savings_balance(1000000);
            create_account.set_initial_checking_balance(1000000);
            payload.set_create_account(create_account);

            self.current_account += 1;

            Some(payload)
        } else if self.current_transaction < self.num_transactions {
            let mut payload =  SmallbankTransactionPayload::new();

            let payload_type = match self.rng.gen_range(2, 7) {
                2 => SBPayloadType::DEPOSIT_CHECKING,
                3 => SBPayloadType::WRITE_CHECK,
                4 => SBPayloadType::TRANSACT_SAVINGS,
                5 => SBPayloadType::SEND_PAYMENT,
                6 => SBPayloadType::AMALGAMATE,
                _ => panic!("Should not have generated outside of [2, 7)")
            };

            payload.set_payload_type(payload_type);

            match payload_type {
                SBPayloadType::DEPOSIT_CHECKING => {
                    let data = make_smallbank_deposit_checking_txn(&mut self.rng, self.num_accounts);
                    payload.set_deposit_checking(data);
                },
                SBPayloadType::WRITE_CHECK => {
                    let data = make_smallbank_write_check_txn(&mut self.rng, self.num_accounts);
                    payload.set_write_check(data);
                },
                SBPayloadType::TRANSACT_SAVINGS => {
                    let data = make_smallbank_transact_savings_txn(&mut self.rng, self.num_accounts);
                    payload.set_transact_savings(data);
                },
                SBPayloadType::SEND_PAYMENT => {
                    let data = make_smallbank_send_payment_txn(&mut self.rng, self.num_accounts);
                    payload.set_send_payment(data);
                },
                SBPayloadType::AMALGAMATE => {
                    let data = make_smallbank_amalgamate_txn(&mut self.rng, self.num_accounts);
                    payload.set_amalgamate(data);
                },
                _ => panic!("Should not have generated outside of [2, 7)")
            };

            self.current_transaction += 1;

            Some(payload)
        } else {
            None
        }
    }
}

impl From<smallbank::SmallbankTransactionPayload> for Yaml {
    fn from(payload: smallbank::SmallbankTransactionPayload) -> Self {

        match payload.payload_type {
            SBPayloadType::CREATE_ACCOUNT => {
                let data = payload.get_create_account();
                yaml_map!{
                    "transaction_type" => Yaml::from_str("create_account"),
                    "customer_id" => Yaml::Integer(data.customer_id as i64),
                    "customer_name" => Yaml::String(data.customer_name.clone()),
                    "initial_savings_balance" =>
                        Yaml::Integer(data.initial_savings_balance as i64),
                    "initial_checking_balance" =>
                        Yaml::Integer(data.initial_checking_balance as i64)}
            },
            SBPayloadType::DEPOSIT_CHECKING => {
                let data = payload.get_deposit_checking();
                yaml_map!{
                    "transaction_type" => Yaml::from_str("deposit_checking"),
                    "customer_id" => Yaml::Integer(data.customer_id as i64),
                    "amount" => Yaml::Integer(data.amount as i64)}
            },
            SBPayloadType::WRITE_CHECK => {
                let data  = payload.get_write_check();
                yaml_map!{
                    "transaction_type" => Yaml::from_str("write_check"),
                    "customer_id" => Yaml::Integer(data.customer_id as i64),
                    "amount" => Yaml::Integer(data.amount as i64)}
            },
            SBPayloadType::TRANSACT_SAVINGS => {
                let data = payload.get_transact_savings();
                yaml_map!{
                    "transaction_type" => Yaml::from_str("transact_savings"),
                    "customer_id" => Yaml::Integer(data.customer_id as i64),
                    "amount" => Yaml::Integer(data.amount as i64)}
            },
            SBPayloadType::SEND_PAYMENT => {
                let data = payload.get_send_payment();
                yaml_map!{
                    "transaction_type" => Yaml::from_str("send_payment"),
                    "source_customer_id" => Yaml::Integer(data.source_customer_id as i64),
                    "dest_customer_id" => Yaml::Integer(data.dest_customer_id as i64),
                    "amount" => Yaml::Integer(data.amount as i64)}
            },
            SBPayloadType::AMALGAMATE => {
                let data = payload.get_amalgamate();
                yaml_map!{
                    "transaction_type" => Yaml::from_str("amalgamate"),
                    "source_customer_id" => Yaml::Integer(data.source_customer_id as i64),
                    "dest_customer_id" => Yaml::Integer(data.dest_customer_id as i64)}
            },
        }
    }
}

fn make_smallbank_deposit_checking_txn(rng: &mut StdRng, num_accounts: usize)
    -> smallbank::SmallbankTransactionPayload_DepositCheckingTransactionData
{
    let mut payload =
        smallbank::SmallbankTransactionPayload_DepositCheckingTransactionData::new();
    payload.set_customer_id(rng.gen_range(0, num_accounts as u32));
    payload.set_amount(rng.gen_range(10, 200));

    payload
}

fn make_smallbank_write_check_txn(rng: &mut StdRng, num_accounts: usize)
    -> smallbank::SmallbankTransactionPayload_WriteCheckTransactionData
{
    let mut payload =
        smallbank::SmallbankTransactionPayload_WriteCheckTransactionData::new();
    payload.set_customer_id(rng.gen_range(0, num_accounts as u32));
    payload.set_amount(rng.gen_range(10, 200));

    payload
}

fn make_smallbank_transact_savings_txn(rng: &mut StdRng, num_accounts: usize)
    -> smallbank::SmallbankTransactionPayload_TransactSavingsTransactionData
{
    let mut payload =
        smallbank::SmallbankTransactionPayload_TransactSavingsTransactionData::new();
    payload.set_customer_id(rng.gen_range(0, num_accounts as u32));
    payload.set_amount(rng.gen_range(10, 200));

    payload
}

fn make_smallbank_send_payment_txn(rng: &mut StdRng, num_accounts: usize)
    -> smallbank::SmallbankTransactionPayload_SendPaymentTransactionData
{
    let mut payload =
        smallbank::SmallbankTransactionPayload_SendPaymentTransactionData::new();
    payload.set_source_customer_id(rng.gen_range(0, num_accounts as u32));
    payload.set_dest_customer_id(rng.gen_range(0, num_accounts as u32));
    payload.set_amount(rng.gen_range(10, 200));

    payload
}

fn make_smallbank_amalgamate_txn(rng: &mut StdRng, num_accounts: usize)
    -> smallbank::SmallbankTransactionPayload_AmalgamateTransactionData
{
    let mut payload =
        smallbank::SmallbankTransactionPayload_AmalgamateTransactionData::new();
    payload.set_source_customer_id(rng.gen_range(0, num_accounts as u32));
    payload.set_dest_customer_id(rng.gen_range(0, num_accounts as u32));

    payload
}

#[derive(Debug)]
pub enum PlaylistError {
    IoError(StdIoError),
    YamlOutputError(EmitError),
}

impl fmt::Display for PlaylistError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match *self {
            PlaylistError::IoError(ref err) =>
                write!(f, "Error occurred writing messages: {}", err),
            PlaylistError::YamlOutputError(_) =>
                    write!(f, "Error occurred generating YAML output"),
        }
    }
}

impl error::Error for PlaylistError {
    fn description(&self) -> &str {
        match *self {
            PlaylistError::IoError(ref err) => err.description(),
            PlaylistError::YamlOutputError(_) => "Yaml Output Error",
        }
    }

    fn cause(&self) -> Option<&error::Error> {
        match *self {
            PlaylistError::IoError(ref err) => Some(err),
            PlaylistError::YamlOutputError(_) => None,
        }
    }
}


struct FmtWriter<'a> {
    writer: Box<&'a mut Write>
}

impl<'a> FmtWriter<'a> {
    pub fn new(writer: &'a mut Write) -> Self {
        FmtWriter {
            writer: Box::new(writer)
        }
    }
}

impl<'a> fmt::Write for FmtWriter<'a> {
    fn write_str(&mut self, s: &str) -> Result<(), fmt::Error> {
        let mut w = &mut *self.writer;
        w.write_all(s.as_bytes()).map_err(|_| fmt::Error::default())
    }
}

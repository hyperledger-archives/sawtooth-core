/*
 * Copyright 2018 Intel Corporation
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

use protobuf;
use protobuf::{Message as ProtobufMessage, ProtobufError};
use rand;
use rand::Rng;

use consensus::driver::Driver;
use consensus::engine::*;
use consensus::service::Service;

use messaging::stream::MessageConnection;
use messaging::stream::MessageSender;
use messaging::stream::ReceiveError;
use messaging::stream::SendError;
use messaging::zmq_stream::ZmqMessageConnection;
use messaging::zmq_stream::ZmqMessageSender;

use messages::consensus::*;
use messages::validator::{Message, Message_MessageType};

use std::sync::{Arc, mpsc::{channel, RecvTimeoutError, Sender}};

/// Generates a random correlation id for use in Message
fn generate_correlation_id() -> String {
    const LENGTH: usize = 16;
    rand::thread_rng().gen_ascii_chars().take(LENGTH).collect()
}

pub struct ZmqDriver {
    engine: Arc<Box<Engine>>,
    exit: Exit,
}

impl Driver for ZmqDriver {
    fn new(engine: Box<Engine>) -> Self {
        ZmqDriver {
            engine: Arc::new(engine),
            exit: Exit::new(),
        }
    }

    fn start(&self, endpoint: &str) -> Result<(), Error> {
        let validator_connection = ZmqMessageConnection::new(endpoint);
        let (mut validator_sender, validator_receiver) = validator_connection.create();

        register(
            &mut validator_sender,
            self.engine.name(),
            self.engine.version(),
        )?;

        let validator_sender_clone = validator_sender.clone();
        let (mut update_sender, update_receiver) = channel();
        let engine = Arc::clone(&self.engine);
        let engine_thread = ::std::thread::spawn(move || {
            engine.start(
                update_receiver,
                Box::new(ZmqService::new(
                    validator_sender_clone,
                    ::std::time::Duration::from_secs(10),
                    engine.name(),
                    engine.version(),
                )),
            );
        });

        loop {
            match validator_receiver.recv_timeout(::std::time::Duration::from_millis(100)) {
                Err(RecvTimeoutError::Timeout) => {
                    if self.exit.get() {
                        self.engine.stop();
                        break;
                    }
                }
                Err(RecvTimeoutError::Disconnected) => {
                    error!("Sender disconnected");
                    break;
                }
                Ok(Err(err)) => {
                    error!("Unexpected error while receiving: {}", err);
                    break;
                }
                Ok(Ok(msg)) => {
                    if let Err(err) = handle_update(&msg, &mut validator_sender, &mut update_sender)
                    {
                        error!("Error handling message: {}", err);
                    }
                    if self.exit.get() {
                        self.engine.stop();
                        break;
                    }
                }
            }
        }

        engine_thread.join().expect("Engine panicked");

        Ok(())
    }

    fn stop(&self) {
        self.exit.set();
    }
}

pub fn register(sender: &mut MessageSender, name: String, version: String) -> Result<(), Error> {
    let mut request = ConsensusRegisterRequest::new();
    request.set_name(name);
    request.set_version(version);

    let mut future = sender.send(
        Message_MessageType::CONSENSUS_REGISTER_REQUEST,
        &generate_correlation_id(),
        &request.write_to_bytes()?,
    )?;

    let msg = future.get_timeout(::std::time::Duration::from_secs(10))?;
    match msg.get_message_type() {
        Message_MessageType::CONSENSUS_REGISTER_RESPONSE => {
            let response: ConsensusRegisterResponse =
                protobuf::parse_from_bytes(msg.get_content())?;
            match response.get_status() {
                ConsensusRegisterResponse_Status::OK => Ok(()),
                status => Err(Error::ReceiveError(format!(
                    "Registration failed with status {:?}",
                    status
                ))),
            }
        }
        unexpected => Err(Error::ReceiveError(format!(
            "Received unexpected message type: {:?}",
            unexpected
        ))),
    }
}

fn handle_update(
    msg: &Message,
    validator_sender: &mut MessageSender,
    update_sender: &mut Sender<Update>,
) -> Result<(), Error> {
    use self::Message_MessageType::*;

    let update = match msg.get_message_type() {
        CONSENSUS_NOTIFY_PEER_CONNECTED => {
            let mut request: ConsensusNotifyPeerConnected =
                protobuf::parse_from_bytes(msg.get_content())?;
            Update::PeerConnected(request.take_peer_info().into())
        }
        CONSENSUS_NOTIFY_PEER_DISCONNECTED => {
            let mut request: ConsensusNotifyPeerDisconnected =
                protobuf::parse_from_bytes(msg.get_content())?;
            Update::PeerDisconnected(request.take_peer_id().into())
        }
        CONSENSUS_NOTIFY_PEER_MESSAGE => {
            let mut request: ConsensusNotifyPeerMessage =
                protobuf::parse_from_bytes(msg.get_content())?;
            Update::PeerMessage(request.take_message().into())
        }
        CONSENSUS_NOTIFY_BLOCK_NEW => {
            let mut request: ConsensusNotifyBlockNew =
                protobuf::parse_from_bytes(msg.get_content())?;
            Update::BlockNew(request.take_block().into())
        }
        CONSENSUS_NOTIFY_BLOCK_VALID => {
            let mut request: ConsensusNotifyBlockValid =
                protobuf::parse_from_bytes(msg.get_content())?;
            Update::BlockValid(request.take_block_id().into())
        }
        CONSENSUS_NOTIFY_BLOCK_INVALID => {
            let mut request: ConsensusNotifyBlockInvalid =
                protobuf::parse_from_bytes(msg.get_content())?;
            Update::BlockInvalid(request.take_block_id().into())
        }
        CONSENSUS_NOTIFY_BLOCK_COMMIT => {
            let mut request: ConsensusNotifyBlockCommit =
                protobuf::parse_from_bytes(msg.get_content())?;
            Update::BlockCommit(request.take_block_id().into())
        }
        unexpected => {
            return Err(Error::ReceiveError(format!(
                "Received unexpected message type: {:?}",
                unexpected
            )))
        }
    };

    update_sender.send(update)?;
    validator_sender.reply(
        Message_MessageType::CONSENSUS_NOTIFY_ACK,
        msg.get_correlation_id(),
        &[],
    )?;
    Ok(())
}

pub struct ZmqService {
    sender: ZmqMessageSender,
    timeout: ::std::time::Duration,
    name: String,
    version: String,
}

impl ZmqService {
    pub fn new(
        sender: ZmqMessageSender,
        timeout: ::std::time::Duration,
        name: String,
        version: String,
    ) -> Self {
        ZmqService {
            sender,
            timeout,
            name,
            version,
        }
    }

    /// Serialize and send a request, wait for the default timeout, and receive and parse an
    /// expected response.
    pub fn rpc<I: protobuf::Message, O: protobuf::Message>(
        &mut self,
        request: &I,
        request_type: Message_MessageType,
        response_type: Message_MessageType,
    ) -> Result<O, Error> {
        let corr_id = generate_correlation_id();
        let mut future = self.sender
            .send(request_type, &corr_id, &request.write_to_bytes()?)?;

        let msg = future.get_timeout(self.timeout)?;
        let msg_type = msg.get_message_type();
        if msg_type == response_type {
            let response = protobuf::parse_from_bytes(msg.get_content())?;
            Ok(response)
        } else {
            Err(Error::ReceiveError(format!(
                "Received unexpected message type: {:?}",
                msg_type
            )))
        }
    }
}

/// Return Ok(()) if $r.get_status() matches $ok
macro_rules! check_ok {
    ($r:expr, $ok:pat) => {
        match $r.get_status() {
            $ok => Ok(()),
            status => Err(Error::ReceiveError(format!(
                "Failed with status {:?}",
                status
            ))),
        }
    };
}

impl Service for ZmqService {
    fn send_to(
        &mut self,
        peer: &PeerId,
        message_type: &str,
        payload: Vec<u8>,
    ) -> Result<(), Error> {
        let mut message = ConsensusPeerMessage::new();
        message.set_message_type(message_type.into());
        message.set_content(payload);
        message.set_name(self.name.clone());
        message.set_version(self.version.clone());

        let mut request = ConsensusSendToRequest::new();
        request.set_message(message);
        request.set_peer_id((*peer).clone().into());

        let response: ConsensusSendToResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_SEND_TO_REQUEST,
            Message_MessageType::CONSENSUS_SEND_TO_RESPONSE,
        )?;

        check_ok!(response, ConsensusSendToResponse_Status::OK)
    }

    fn broadcast(&mut self, message_type: &str, payload: Vec<u8>) -> Result<(), Error> {
        let mut message = ConsensusPeerMessage::new();
        message.set_message_type(message_type.into());
        message.set_content(payload);

        let mut request = ConsensusBroadcastRequest::new();
        request.set_message(message);

        let response: ConsensusBroadcastResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_BROADCAST_REQUEST,
            Message_MessageType::CONSENSUS_BROADCAST_RESPONSE,
        )?;

        check_ok!(response, ConsensusBroadcastResponse_Status::OK)
    }

    fn initialize_block(&mut self, previous_id: Option<BlockId>) -> Result<(), Error> {
        let mut request = ConsensusInitializeBlockRequest::new();
        if let Some(previous_id) = previous_id {
            request.set_previous_id(previous_id.into());
        }

        let response: ConsensusInitializeBlockResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_INITIALIZE_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_INITIALIZE_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusInitializeBlockResponse_Status::INVALID_STATE {
            return Err(Error::InvalidState(
                "Cannot initialize block in current state".into(),
            ));
        }

        if response.get_status() == ConsensusInitializeBlockResponse_Status::UNKNOWN_BLOCK {
            return Err(Error::UnknownBlock("Block not found".into()));
        }

        check_ok!(response, ConsensusInitializeBlockResponse_Status::OK)
    }

    fn finalize_block(&mut self, data: Vec<u8>) -> Result<BlockId, Error> {
        let mut request = ConsensusFinalizeBlockRequest::new();
        request.set_data(data);

        let mut response: ConsensusFinalizeBlockResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_FINALIZE_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_FINALIZE_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusFinalizeBlockResponse_Status::INVALID_STATE {
            Err(Error::InvalidState(
                "Cannot finalize block in current state".into(),
            ))
        } else {
            check_ok!(response, ConsensusFinalizeBlockResponse_Status::OK)
        }?;

        Ok(response.take_block_id().into())
    }

    fn cancel_block(&mut self) -> Result<(), Error> {
        let request = ConsensusCancelBlockRequest::new();

        let response: ConsensusCancelBlockResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_CANCEL_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_CANCEL_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusCancelBlockResponse_Status::INVALID_STATE {
            Err(Error::InvalidState(
                "Cannot cancel block in current state".into(),
            ))
        } else {
            check_ok!(response, ConsensusCancelBlockResponse_Status::OK)
        }
    }

    fn check_blocks(&mut self, priority: Vec<BlockId>) -> Result<(), Error> {
        let mut request = ConsensusCheckBlockRequest::new();
        request.set_block_ids(protobuf::RepeatedField::from_vec(
            priority.into_iter().map(Vec::from).collect(),
        ));

        let response: ConsensusCheckBlockResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_CHECK_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_CHECK_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusCheckBlockResponse_Status::UNKNOWN_BLOCK {
            Err(Error::UnknownBlock("Block not found".into()))
        } else {
            check_ok!(response, ConsensusCheckBlockResponse_Status::OK)
        }
    }

    fn commit_block(&mut self, block_id: BlockId) -> Result<(), Error> {
        let mut request = ConsensusCommitBlockRequest::new();
        request.set_block_id(block_id.into());

        let response: ConsensusCommitBlockResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_COMMIT_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_COMMIT_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusCommitBlockResponse_Status::UNKNOWN_BLOCK {
            Err(Error::UnknownBlock("Block not found".into()))
        } else {
            check_ok!(response, ConsensusCommitBlockResponse_Status::OK)
        }
    }

    fn ignore_block(&mut self, block_id: BlockId) -> Result<(), Error> {
        let mut request = ConsensusIgnoreBlockRequest::new();
        request.set_block_id(block_id.into());

        let response: ConsensusIgnoreBlockResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_IGNORE_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_IGNORE_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusIgnoreBlockResponse_Status::UNKNOWN_BLOCK {
            Err(Error::UnknownBlock("Block not found".into()))
        } else {
            check_ok!(response, ConsensusIgnoreBlockResponse_Status::OK)
        }
    }

    fn fail_block(&mut self, block_id: BlockId) -> Result<(), Error> {
        let mut request = ConsensusFailBlockRequest::new();
        request.set_block_id(block_id.into());

        let response: ConsensusFailBlockResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_FAIL_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_FAIL_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusFailBlockResponse_Status::UNKNOWN_BLOCK {
            Err(Error::UnknownBlock("Block not found".into()))
        } else {
            check_ok!(response, ConsensusFailBlockResponse_Status::OK)
        }
    }

    fn get_blocks(&mut self, block_ids: Vec<BlockId>) -> Result<Vec<Block>, Error> {
        let mut request = ConsensusBlocksGetRequest::new();
        request.set_block_ids(protobuf::RepeatedField::from_vec(
            block_ids.into_iter().map(Vec::from).collect(),
        ));

        let mut response: ConsensusBlocksGetResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_BLOCKS_GET_REQUEST,
            Message_MessageType::CONSENSUS_BLOCKS_GET_RESPONSE,
        )?;

        if response.get_status() == ConsensusBlocksGetResponse_Status::UNKNOWN_BLOCK {
            Err(Error::UnknownBlock("Block not found".into()))
        } else {
            check_ok!(response, ConsensusBlocksGetResponse_Status::OK)
        }?;

        Ok(response
            .take_blocks()
            .into_iter()
            .map(Block::from)
            .collect())
    }

    fn get_settings(&mut self, block_id: BlockId, keys: Vec<String>) -> Result<Vec<String>, Error> {
        let mut request = ConsensusSettingsGetRequest::new();
        request.set_block_id(block_id.into());
        request.set_keys(protobuf::RepeatedField::from_vec(keys));

        let mut response: ConsensusSettingsGetResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_SETTINGS_GET_REQUEST,
            Message_MessageType::CONSENSUS_SETTINGS_GET_RESPONSE,
        )?;

        if response.get_status() == ConsensusSettingsGetResponse_Status::UNKNOWN_BLOCK {
            Err(Error::UnknownBlock("Block not found".into()))
        } else {
            check_ok!(response, ConsensusSettingsGetResponse_Status::OK)
        }?;

        Ok(response
            .take_entries()
            .into_iter()
            .map(|mut entry| entry.take_value())
            .collect())
    }

    fn get_state(
        &mut self,
        block_id: BlockId,
        addresses: Vec<String>,
    ) -> Result<Vec<Vec<u8>>, Error> {
        let mut request = ConsensusStateGetRequest::new();
        request.set_block_id(block_id.into());
        request.set_addresses(protobuf::RepeatedField::from_vec(addresses));

        let mut response: ConsensusStateGetResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_STATE_GET_REQUEST,
            Message_MessageType::CONSENSUS_STATE_GET_RESPONSE,
        )?;

        if response.get_status() == ConsensusStateGetResponse_Status::UNKNOWN_BLOCK {
            Err(Error::UnknownBlock("Block not found".into()))
        } else {
            check_ok!(response, ConsensusStateGetResponse_Status::OK)
        }?;

        Ok(response
            .take_entries()
            .into_iter()
            .map(|mut entry| entry.take_data())
            .collect())
    }
}

impl From<ConsensusBlock> for Block {
    fn from(mut c_block: ConsensusBlock) -> Block {
        Block {
            block_id: c_block.take_block_id().into(),
            previous_id: c_block.take_previous_id().into(),
            signer_id: c_block.take_signer_id().into(),
            block_num: c_block.get_block_num(),
            payload: c_block.take_payload(),
        }
    }
}

impl From<ConsensusPeerInfo> for PeerInfo {
    fn from(mut c_peer_info: ConsensusPeerInfo) -> PeerInfo {
        PeerInfo {
            peer_id: c_peer_info.take_peer_id().into(),
        }
    }
}

impl From<ConsensusPeerMessage> for PeerMessage {
    fn from(mut c_msg: ConsensusPeerMessage) -> PeerMessage {
        PeerMessage {
            message_type: c_msg.take_message_type(),
            content: c_msg.take_content(),
        }
    }
}

impl From<ProtobufError> for Error {
    fn from(error: ProtobufError) -> Error {
        use self::ProtobufError::*;
        match error {
            IoError(err) => Error::EncodingError(format!("{}", err)),
            WireError(err) => Error::EncodingError(format!("{:?}", err)),
            Utf8(err) => Error::EncodingError(format!("{}", err)),
            MessageNotInitialized { message: err } => Error::EncodingError(format!("{}", err)),
        }
    }
}

impl From<SendError> for Error {
    fn from(error: SendError) -> Error {
        Error::SendError(format!("{}", error))
    }
}

impl From<::std::sync::mpsc::SendError<Update>> for Error {
    fn from(error: ::std::sync::mpsc::SendError<Update>) -> Error {
        Error::SendError(format!("{}", error))
    }
}

impl From<ReceiveError> for Error {
    fn from(error: ReceiveError) -> Error {
        Error::ReceiveError(format!("{}", error))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use consensus::engine::tests::MockEngine;
    use std::default::Default;
    use std::sync::Mutex;
    use zmq;

    fn send_req_rep<I: protobuf::Message, O: protobuf::Message>(
        connection_id: &[u8],
        socket: &zmq::Socket,
        request: I,
        request_type: Message_MessageType,
        response_type: Message_MessageType,
    ) -> O {
        let correlation_id = generate_correlation_id();
        let mut msg = Message::new();
        msg.set_message_type(request_type);
        msg.set_correlation_id(correlation_id.clone());
        msg.set_content(request.write_to_bytes().unwrap());
        socket
            .send_multipart(&[connection_id, &msg.write_to_bytes().unwrap()], 0)
            .unwrap();
        let msg: Message =
            protobuf::parse_from_bytes(&socket.recv_multipart(0).unwrap()[1]).unwrap();
        assert!(msg.get_message_type() == response_type);
        protobuf::parse_from_bytes(&msg.get_content()).unwrap()
    }

    fn recv_rep<I: protobuf::Message, O: protobuf::Message>(
        socket: &zmq::Socket,
        request_type: Message_MessageType,
        response: I,
        response_type: Message_MessageType,
    ) -> (Vec<u8>, O) {
        let mut parts = socket.recv_multipart(0).unwrap();
        assert!(parts.len() == 2);

        let mut msg: Message = protobuf::parse_from_bytes(&parts.pop().unwrap()).unwrap();
        let connection_id = parts.pop().unwrap();
        assert!(msg.get_message_type() == request_type);
        let request: O = protobuf::parse_from_bytes(&msg.get_content()).unwrap();

        let correlation_id = msg.take_correlation_id();
        let mut msg = Message::new();
        msg.set_message_type(response_type);
        msg.set_correlation_id(correlation_id);
        msg.set_content(response.write_to_bytes().unwrap());
        socket
            .send_multipart(&[&connection_id, &msg.write_to_bytes().unwrap()], 0)
            .unwrap();

        (connection_id, request)
    }

    #[test]
    fn test_zmq_driver() {
        let ctx = zmq::Context::new();
        let socket = ctx.socket(zmq::ROUTER).expect("Failed to create context");
        socket
            .bind("tcp://127.0.0.1:*")
            .expect("Failed to bind socket");
        let addr = socket.get_last_endpoint().unwrap().unwrap();

        // Create the mock engine with this vec so we can refer to it later. Once we put the engine
        // in a box, it is hard to get the vec back out.
        let calls = Arc::new(Mutex::new(Vec::new()));

        // We are going to run two threads to simulate the validator and the driver
        let driver = Arc::new(ZmqDriver::new(Box::new(MockEngine::with(calls.clone()))));

        let driver_clone = driver.clone();
        let driver_thread = ::std::thread::spawn(move || {
            driver_clone.start(&addr).unwrap();
        });

        let mut response = ConsensusRegisterResponse::new();
        response.set_status(ConsensusRegisterResponse_Status::OK);
        let (connection_id, request): (_, ConsensusRegisterRequest) = recv_rep(
            &socket,
            Message_MessageType::CONSENSUS_REGISTER_REQUEST,
            response,
            Message_MessageType::CONSENSUS_REGISTER_RESPONSE,
        );
        assert!("mock" == request.get_name());
        assert!("0" == request.get_version());

        let _: ConsensusNotifyAck = send_req_rep(
            &connection_id,
            &socket,
            ConsensusNotifyPeerConnected::new(),
            Message_MessageType::CONSENSUS_NOTIFY_PEER_CONNECTED,
            Message_MessageType::CONSENSUS_NOTIFY_ACK,
        );

        let _: ConsensusNotifyAck = send_req_rep(
            &connection_id,
            &socket,
            ConsensusNotifyPeerDisconnected::new(),
            Message_MessageType::CONSENSUS_NOTIFY_PEER_DISCONNECTED,
            Message_MessageType::CONSENSUS_NOTIFY_ACK,
        );

        let _: ConsensusNotifyAck = send_req_rep(
            &connection_id,
            &socket,
            ConsensusNotifyPeerMessage::new(),
            Message_MessageType::CONSENSUS_NOTIFY_PEER_MESSAGE,
            Message_MessageType::CONSENSUS_NOTIFY_ACK,
        );

        let _: ConsensusNotifyAck = send_req_rep(
            &connection_id,
            &socket,
            ConsensusNotifyBlockNew::new(),
            Message_MessageType::CONSENSUS_NOTIFY_BLOCK_NEW,
            Message_MessageType::CONSENSUS_NOTIFY_ACK,
        );

        let _: ConsensusNotifyAck = send_req_rep(
            &connection_id,
            &socket,
            ConsensusNotifyBlockValid::new(),
            Message_MessageType::CONSENSUS_NOTIFY_BLOCK_VALID,
            Message_MessageType::CONSENSUS_NOTIFY_ACK,
        );

        let _: ConsensusNotifyAck = send_req_rep(
            &connection_id,
            &socket,
            ConsensusNotifyBlockInvalid::new(),
            Message_MessageType::CONSENSUS_NOTIFY_BLOCK_INVALID,
            Message_MessageType::CONSENSUS_NOTIFY_ACK,
        );

        let _: ConsensusNotifyAck = send_req_rep(
            &connection_id,
            &socket,
            ConsensusNotifyBlockCommit::new(),
            Message_MessageType::CONSENSUS_NOTIFY_BLOCK_COMMIT,
            Message_MessageType::CONSENSUS_NOTIFY_ACK,
        );

        // Shut it down
        driver.stop();
        driver_thread.join().expect("Driver thread panicked");

        // Assert we did what we expected
        let final_calls = calls.lock().unwrap();
        assert!(contains(&*final_calls, "start"));
        assert!(contains(&*final_calls, "PeerConnected"));
        assert!(contains(&*final_calls, "PeerDisconnected"));
        assert!(contains(&*final_calls, "PeerMessage"));
        assert!(contains(&*final_calls, "BlockNew"));
        assert!(contains(&*final_calls, "BlockValid"));
        assert!(contains(&*final_calls, "BlockInvalid"));
        assert!(contains(&*final_calls, "BlockCommit"));
        assert!(contains(&*final_calls, "stop"));
    }

    fn contains(calls: &Vec<String>, expected: &str) -> bool {
        for call in calls {
            if expected == call.as_str() {
                return true;
            }
        }
        false
    }

    macro_rules! service_test {
        (
            $socket:expr,
            $rep:expr,
            $status:expr,
            $rep_msg_type:expr,
            $req_type:ty,
            $req_msg_type:expr
        ) => {
            let mut response = $rep;
            response.set_status($status);
            let (_, _): (_, $req_type) =
                recv_rep($socket, $req_msg_type, response, $rep_msg_type);
        };
    }

    #[test]
    fn test_zmq_service() {
        let ctx = zmq::Context::new();
        let socket = ctx.socket(zmq::ROUTER).expect("Failed to create context");
        socket
            .bind("tcp://127.0.0.1:*")
            .expect("Failed to bind socket");
        let addr = socket.get_last_endpoint().unwrap().unwrap();

        let svc_thread = ::std::thread::spawn(move || {
            let connection = ZmqMessageConnection::new(&addr);
            let (sender, _) = connection.create();
            let mut svc = ZmqService::new(
                sender,
                ::std::time::Duration::from_secs(10),
                "mock".into(),
                "0".into(),
            );

            svc.send_to(&Default::default(), Default::default(), Default::default())
                .unwrap();
            svc.broadcast(Default::default(), Default::default())
                .unwrap();

            svc.initialize_block(Some(Default::default())).unwrap();
            svc.finalize_block(Default::default()).unwrap();
            svc.cancel_block().unwrap();

            svc.check_blocks(Default::default()).unwrap();
            svc.commit_block(Default::default()).unwrap();
            svc.ignore_block(Default::default()).unwrap();
            svc.fail_block(Default::default()).unwrap();

            svc.get_blocks(Default::default()).unwrap();
            svc.get_settings(Default::default(), Default::default())
                .unwrap();
            svc.get_state(Default::default(), Default::default())
                .unwrap();
        });

        service_test!(
            &socket,
            ConsensusSendToResponse::new(),
            ConsensusSendToResponse_Status::OK,
            Message_MessageType::CONSENSUS_SEND_TO_RESPONSE,
            ConsensusSendToRequest,
            Message_MessageType::CONSENSUS_SEND_TO_REQUEST
        );

        service_test!(
            &socket,
            ConsensusBroadcastResponse::new(),
            ConsensusBroadcastResponse_Status::OK,
            Message_MessageType::CONSENSUS_BROADCAST_RESPONSE,
            ConsensusBroadcastRequest,
            Message_MessageType::CONSENSUS_BROADCAST_REQUEST
        );

        service_test!(
            &socket,
            ConsensusInitializeBlockResponse::new(),
            ConsensusInitializeBlockResponse_Status::OK,
            Message_MessageType::CONSENSUS_INITIALIZE_BLOCK_RESPONSE,
            ConsensusInitializeBlockRequest,
            Message_MessageType::CONSENSUS_INITIALIZE_BLOCK_REQUEST
        );

        service_test!(
            &socket,
            ConsensusFinalizeBlockResponse::new(),
            ConsensusFinalizeBlockResponse_Status::OK,
            Message_MessageType::CONSENSUS_FINALIZE_BLOCK_RESPONSE,
            ConsensusFinalizeBlockRequest,
            Message_MessageType::CONSENSUS_FINALIZE_BLOCK_REQUEST
        );

        service_test!(
            &socket,
            ConsensusCancelBlockResponse::new(),
            ConsensusCancelBlockResponse_Status::OK,
            Message_MessageType::CONSENSUS_CANCEL_BLOCK_RESPONSE,
            ConsensusCancelBlockRequest,
            Message_MessageType::CONSENSUS_CANCEL_BLOCK_REQUEST
        );

        service_test!(
            &socket,
            ConsensusCheckBlockResponse::new(),
            ConsensusCheckBlockResponse_Status::OK,
            Message_MessageType::CONSENSUS_CHECK_BLOCK_RESPONSE,
            ConsensusCheckBlockRequest,
            Message_MessageType::CONSENSUS_CHECK_BLOCK_REQUEST
        );

        service_test!(
            &socket,
            ConsensusCommitBlockResponse::new(),
            ConsensusCommitBlockResponse_Status::OK,
            Message_MessageType::CONSENSUS_COMMIT_BLOCK_RESPONSE,
            ConsensusCommitBlockRequest,
            Message_MessageType::CONSENSUS_COMMIT_BLOCK_REQUEST
        );

        service_test!(
            &socket,
            ConsensusIgnoreBlockResponse::new(),
            ConsensusIgnoreBlockResponse_Status::OK,
            Message_MessageType::CONSENSUS_IGNORE_BLOCK_RESPONSE,
            ConsensusIgnoreBlockRequest,
            Message_MessageType::CONSENSUS_IGNORE_BLOCK_REQUEST
        );

        service_test!(
            &socket,
            ConsensusFailBlockResponse::new(),
            ConsensusFailBlockResponse_Status::OK,
            Message_MessageType::CONSENSUS_FAIL_BLOCK_RESPONSE,
            ConsensusFailBlockRequest,
            Message_MessageType::CONSENSUS_FAIL_BLOCK_REQUEST
        );

        service_test!(
            &socket,
            ConsensusBlocksGetResponse::new(),
            ConsensusBlocksGetResponse_Status::OK,
            Message_MessageType::CONSENSUS_BLOCKS_GET_RESPONSE,
            ConsensusBlocksGetRequest,
            Message_MessageType::CONSENSUS_BLOCKS_GET_REQUEST
        );

        service_test!(
            &socket,
            ConsensusSettingsGetResponse::new(),
            ConsensusSettingsGetResponse_Status::OK,
            Message_MessageType::CONSENSUS_SETTINGS_GET_RESPONSE,
            ConsensusSettingsGetRequest,
            Message_MessageType::CONSENSUS_SETTINGS_GET_REQUEST
        );

        service_test!(
            &socket,
            ConsensusStateGetResponse::new(),
            ConsensusStateGetResponse_Status::OK,
            Message_MessageType::CONSENSUS_STATE_GET_RESPONSE,
            ConsensusStateGetRequest,
            Message_MessageType::CONSENSUS_STATE_GET_REQUEST
        );

        svc_thread.join().unwrap();
    }
}

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

use consensus::service::Service;
use consensus::engine::{Block, Engine, Error, Exit, PeerInfo, PeerUpdate};
use consensus::driver::Driver;

use messaging::stream::MessageConnection;
use messaging::stream::MessageSender;
use messaging::zmq_stream::ZmqMessageSender;
use messaging::stream::SendError;
use messaging::stream::ReceiveError;
use messaging::zmq_stream::ZmqMessageConnection;

use messages::consensus::*;
use messages::validator::{Message, Message_MessageType};

use std::sync::{Arc, mpsc::RecvTimeoutError};

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
        let connection = ZmqMessageConnection::new(endpoint);
        let (mut sender, receiver) = connection.create();

        self.register(&mut sender, self.engine.name(), self.engine.version())?;

        let sender_clone = sender.clone();
        let engine = self.engine.clone();
        let engine_thread = ::std::thread::spawn(move || {
            engine.start(Box::new(ZmqService::new(
                sender_clone,
                ::std::time::Duration::from_secs(10),
            )));
        });

        loop {
            match receiver.recv_timeout(::std::time::Duration::from_millis(100)) {
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
                    if let Err(err) = self.handle_msg(msg, &mut sender) {
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

impl ZmqDriver {
    pub fn register(
        &self,
        sender: &mut MessageSender,
        name: String,
        version: String,
    ) -> Result<(), Error> {
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
            unexpected => {
                return Err(Error::ReceiveError(format!(
                    "Received unexpected message type: {:?}",
                    unexpected
                )))
            }
        }
    }

    fn handle_msg(&self, msg: Message, sender: &mut MessageSender) -> Result<(), Error> {
        match msg.get_message_type() {
            Message_MessageType::CONSENSUS_ON_NEW_BLOCK_RECEIVED_REQUEST => {
                let mut request: ConsensusOnNewBlockReceivedRequest =
                    protobuf::parse_from_bytes(msg.get_content())?;

                let mut response = ConsensusOnNewBlockReceivedResponse::new();
                response.set_status(ConsensusOnNewBlockReceivedResponse_Status::OK);
                sender.reply(
                    Message_MessageType::CONSENSUS_ON_NEW_BLOCK_RECEIVED_RESPONSE,
                    msg.get_correlation_id(),
                    &response.write_to_bytes()?,
                )?;

                self.engine.block(request.take_block().into());
            }
            Message_MessageType::CONSENSUS_ON_MESSAGE_RECEIVED_REQUEST => {
                let mut request: ConsensusOnMessageReceivedRequest =
                    protobuf::parse_from_bytes(msg.get_content())?;

                let mut response = ConsensusOnMessageReceivedResponse::new();
                response.set_status(ConsensusOnMessageReceivedResponse_Status::OK);
                sender.reply(
                    Message_MessageType::CONSENSUS_ON_MESSAGE_RECEIVED_RESPONSE,
                    msg.get_correlation_id(),
                    &response.write_to_bytes()?,
                )?;

                let mut message = request.take_message();
                self.engine
                    .message(message.take_message_type(), message.take_payload());
            }
            Message_MessageType::CONSENSUS_ON_PEER_UPDATE_REQUEST => {
                let mut request: ConsensusOnPeerUpdateRequest =
                    protobuf::parse_from_bytes(msg.get_content())?;

                let mut response = ConsensusOnPeerUpdateResponse::new();
                response.set_status(ConsensusOnPeerUpdateResponse_Status::OK);
                sender.reply(
                    Message_MessageType::CONSENSUS_ON_PEER_UPDATE_RESPONSE,
                    msg.get_correlation_id(),
                    &response.write_to_bytes()?,
                )?;

                self.engine.peer(request.take_peer_update().into());
            }
            unexpected => {
                return Err(Error::ReceiveError(format!(
                    "Received unexpected message type: {:?}",
                    unexpected
                )))
            }
        };
        Ok(())
    }
}

pub struct ZmqService {
    sender: ZmqMessageSender,
    timeout: ::std::time::Duration,
}

impl ZmqService {
    pub fn new(sender: ZmqMessageSender, timeout: ::std::time::Duration) -> Self {
        ZmqService { sender, timeout }
    }

    /// Serialize and send a request, wait for the default timeout, and receive and parse an
    /// expected response.
    pub fn rpc<I: protobuf::Message, O: protobuf::Message + protobuf::MessageStatic>(
        &mut self,
        request: I,
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
            status => Err(Error::ReceiveError(format!("Failed with status {:?}", status))),
        }
    }
}

impl Service for ZmqService {
    fn send_to(&mut self, peer: &str, message_type: &str, payload: Vec<u8>) -> Result<(), Error> {
        let mut message = ConsensusMessage::new();
        message.set_message_type(message_type.into());
        message.set_payload(payload);

        let mut request = ConsensusSendToRequest::new();
        request.set_message(message);
        request.set_peer_id(peer.into());

        let response: ConsensusSendToResponse = self.rpc(
            request,
            Message_MessageType::CONSENSUS_SEND_TO_REQUEST,
            Message_MessageType::CONSENSUS_SEND_TO_RESPONSE,
        )?;

        check_ok!(response, ConsensusSendToResponse_Status::OK)
    }

    fn broadcast(&mut self, message_type: &str, payload: Vec<u8>) -> Result<(), Error> {
        let mut message = ConsensusMessage::new();
        message.set_message_type(message_type.into());
        message.set_payload(payload);

        let mut request = ConsensusBroadcastRequest::new();
        request.set_message(message);

        let response: ConsensusBroadcastResponse = self.rpc(
            request,
            Message_MessageType::CONSENSUS_BROADCAST_REQUEST,
            Message_MessageType::CONSENSUS_BROADCAST_RESPONSE,
        )?;

        check_ok!(response, ConsensusBroadcastResponse_Status::OK)
    }

    fn initialize_block(&mut self, previous_id: Option<String>) -> Result<(), Error> {
        let mut request = ConsensusInitializeBlockRequest::new();
        if let Some(previous_id) = previous_id.as_ref() {
            request.set_previous_id((*previous_id).clone());
        }

        let response: ConsensusInitializeBlockResponse = self.rpc(
            request,
            Message_MessageType::CONSENSUS_INITIALIZE_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_INITIALIZE_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusInitializeBlockResponse_Status::INVALID_STATE {
            return Err(Error::InvalidState(
                "Cannot initialize block in current state".into(),
            ));
        }

        if response.get_status() == ConsensusInitializeBlockResponse_Status::NO_RESOURCE {
            if let Some(previous_id) = previous_id {
                return Err(Error::MissingResource(format!(
                    "No block with id '{}' found",
                    previous_id
                )));
            }
        }

        check_ok!(response, ConsensusInitializeBlockResponse_Status::OK)
    }

    fn finalize_block(&mut self, data: Vec<u8>) -> Result<String, Error> {
        let mut request = ConsensusFinalizeBlockRequest::new();
        request.set_data(data);

        let mut response: ConsensusFinalizeBlockResponse = self.rpc(
            request,
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

        Ok(response.take_block_id())
    }

    fn cancel_block(&mut self) -> Result<(), Error> {
        let request = ConsensusCancelBlockRequest::new();

        let response: ConsensusCancelBlockResponse = self.rpc(
            request,
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

    fn commit_block(&mut self, block_id: String) -> Result<(), Error> {
        let mut request = ConsensusCommitBlockRequest::new();
        request.set_block_id(block_id.clone());

        let response: ConsensusCommitBlockResponse = self.rpc(
            request,
            Message_MessageType::CONSENSUS_COMMIT_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_COMMIT_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusCommitBlockResponse_Status::NO_RESOURCE {
            Err(Error::MissingResource(format!(
                "No block with id '{}' found",
                block_id
            )))
        } else {
            check_ok!(response, ConsensusCommitBlockResponse_Status::OK)
        }
    }

    fn hold_block(&mut self, block_id: String) -> Result<(), Error> {
        let mut request = ConsensusHoldBlockRequest::new();
        request.set_block_id(block_id.clone());

        let response: ConsensusHoldBlockResponse = self.rpc(
            request,
            Message_MessageType::CONSENSUS_HOLD_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_HOLD_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusHoldBlockResponse_Status::NO_RESOURCE {
            Err(Error::MissingResource(format!(
                "No block with id '{}' found",
                block_id
            )))
        } else {
            check_ok!(response, ConsensusHoldBlockResponse_Status::OK)
        }
    }

    fn drop_block(&mut self, block_id: String) -> Result<(), Error> {
        let mut request = ConsensusDropBlockRequest::new();
        request.set_block_id(block_id.clone());

        let response: ConsensusDropBlockResponse = self.rpc(
            request,
            Message_MessageType::CONSENSUS_DROP_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_DROP_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusDropBlockResponse_Status::NO_RESOURCE {
            Err(Error::MissingResource(format!(
                "No block with id '{}' found",
                block_id
            )))
        } else {
            check_ok!(response, ConsensusDropBlockResponse_Status::OK)
        }
    }

    fn fail_block(&mut self, block_id: String) -> Result<(), Error> {
        let mut request = ConsensusFailBlockRequest::new();
        request.set_block_id(block_id.clone());

        let response: ConsensusFailBlockResponse = self.rpc(
            request,
            Message_MessageType::CONSENSUS_FAIL_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_FAIL_BLOCK_RESPONSE,
        )?;

        if response.get_status() == ConsensusFailBlockResponse_Status::NO_RESOURCE {
            Err(Error::MissingResource(format!(
                "No block with id '{}' found",
                block_id
            )))
        } else {
            check_ok!(response, ConsensusFailBlockResponse_Status::OK)
        }
    }

    fn get_block(&mut self, block_id: String) -> Result<Block, Error> {
        let mut request = ConsensusBlockGetRequest::new();
        request.set_block_id(block_id.clone());

        let mut response: ConsensusBlockGetResponse = self.rpc(
            request,
            Message_MessageType::CONSENSUS_BLOCK_GET_REQUEST,
            Message_MessageType::CONSENSUS_BLOCK_GET_RESPONSE,
        )?;

        if response.get_status() == ConsensusBlockGetResponse_Status::NO_RESOURCE {
            Err(Error::MissingResource(format!(
                "No block with id '{}' found",
                block_id
            )))
        } else {
            check_ok!(response, ConsensusBlockGetResponse_Status::OK)
        }?;

        Ok(response.take_block().into())
    }

    // TODO: NO_RESOURCE is probably not a sufficient response status, since you can have a missing
    // block or a missing setting
    fn get_setting(&mut self, block_id: String, setting: String) -> Result<Vec<u8>, Error> {
        let mut request = ConsensusSettingGetRequest::new();
        request.set_block_id(block_id.clone());
        request.set_setting(setting.clone());

        let mut response: ConsensusSettingGetResponse = self.rpc(
            request,
            Message_MessageType::CONSENSUS_SETTING_GET_REQUEST,
            Message_MessageType::CONSENSUS_SETTING_GET_RESPONSE,
        )?;

        if response.get_status() == ConsensusSettingGetResponse_Status::NO_RESOURCE {
            Err(Error::MissingResource(format!(
                "No setting '{}' found for block '{}'",
                setting, block_id
            )))
        } else {
            check_ok!(response, ConsensusSettingGetResponse_Status::OK)
        }?;

        Ok(response.take_data())
    }

    // TODO: NO_RESOURCE is probably not a sufficient response status, since you can have a missing
    // block or a missing setting
    fn get_state(&mut self, block_id: String, address: String) -> Result<Vec<u8>, Error> {
        let mut request = ConsensusStateGetRequest::new();
        request.set_block_id(block_id.clone());
        request.set_address(address.clone());

        let mut response: ConsensusStateGetResponse = self.rpc(
            request,
            Message_MessageType::CONSENSUS_STATE_GET_REQUEST,
            Message_MessageType::CONSENSUS_STATE_GET_RESPONSE,
        )?;

        if response.get_status() == ConsensusStateGetResponse_Status::NO_RESOURCE {
            Err(Error::MissingResource(format!(
                "State not found at address '{}' found for block '{}'",
                address, block_id
            )))
        } else {
            check_ok!(response, ConsensusStateGetResponse_Status::OK)
        }?;

        Ok(response.take_data())
    }
}

impl From<ConsensusBlock> for Block {
    fn from(cblock: ConsensusBlock) -> Block {
        Block {
            block_id: cblock.block_id,
            previous_id: cblock.previous_id,
            signer_id: cblock.signer_id,
            block_num: cblock.block_num,
            consensus: cblock.consensus,
        }
    }
}

impl From<Block> for ConsensusBlock {
    fn from(block: Block) -> ConsensusBlock {
        let mut cblock = ConsensusBlock::new();
        cblock.set_block_id(block.block_id);
        cblock.set_previous_id(block.previous_id);
        cblock.set_signer_id(block.signer_id);
        cblock.set_block_num(block.block_num);
        cblock.set_consensus(block.consensus);
        cblock
    }
}

impl From<ConsensusPeerUpdate> for PeerUpdate {
    fn from(mut cpeerupdate: ConsensusPeerUpdate) -> PeerUpdate {
        match cpeerupdate.get_update() {
            ConsensusPeerUpdate_PeerUpdate::CONNECTED => PeerUpdate::Connected(PeerInfo {
                peer_id: cpeerupdate.take_peer_id(),
            }),
            ConsensusPeerUpdate_PeerUpdate::DISCONNECTED => {
                PeerUpdate::Disconnected(cpeerupdate.take_peer_id())
            }
        }
    }
}

impl From<ProtobufError> for Error {
    fn from(error: ProtobufError) -> Error {
        use self::ProtobufError::*;
        match error {
            IoError(err) => Error::EncodeError(format!("{}", err)),
            WireError(err) => Error::DecodeError(format!("{:?}", err)),
            Utf8(err) => Error::DecodeError(format!("{}", err)),
            MessageNotInitialized { message: err } => Error::EncodeError(format!("{}", err)),
        }
    }
}

impl From<SendError> for Error {
    fn from(error: SendError) -> Error {
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
    use std::default::Default;
    use std::sync::Mutex;
    use consensus::engine::tests::MockEngine;
    use zmq;

    fn send_req_rep<I: protobuf::Message, O: protobuf::Message + protobuf::MessageStatic>(
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

    fn recv_rep<I: protobuf::Message, O: protobuf::Message + protobuf::MessageStatic>(
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

        let request = ConsensusOnNewBlockReceivedRequest::new();
        let response: ConsensusOnNewBlockReceivedResponse = send_req_rep(
            &connection_id,
            &socket,
            request,
            Message_MessageType::CONSENSUS_ON_NEW_BLOCK_RECEIVED_REQUEST,
            Message_MessageType::CONSENSUS_ON_NEW_BLOCK_RECEIVED_RESPONSE,
        );
        assert!(response.get_status() == ConsensusOnNewBlockReceivedResponse_Status::OK);

        let request = ConsensusOnMessageReceivedRequest::new();
        let response: ConsensusOnMessageReceivedResponse = send_req_rep(
            &connection_id,
            &socket,
            request,
            Message_MessageType::CONSENSUS_ON_MESSAGE_RECEIVED_REQUEST,
            Message_MessageType::CONSENSUS_ON_MESSAGE_RECEIVED_RESPONSE,
        );
        assert!(response.get_status() == ConsensusOnMessageReceivedResponse_Status::OK);

        let request = ConsensusOnPeerUpdateRequest::new();
        let response: ConsensusOnPeerUpdateResponse = send_req_rep(
            &connection_id,
            &socket,
            request,
            Message_MessageType::CONSENSUS_ON_PEER_UPDATE_REQUEST,
            Message_MessageType::CONSENSUS_ON_PEER_UPDATE_RESPONSE,
        );
        assert!(response.get_status() == ConsensusOnPeerUpdateResponse_Status::OK);

        // Shut it down
        driver.stop();
        driver_thread.join().expect("Driver thread panicked");

        // Assert we did what we expected
        let final_calls = calls.lock().unwrap();
        assert!(contains(&*final_calls, "start"));
        assert!(contains(&*final_calls, "block"));
        assert!(contains(&*final_calls, "message"));
        assert!(contains(&*final_calls, "peer"));
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
            let (_, _): (_, $req_type) = recv_rep(
                $socket,
                $req_msg_type,
                response,
                $rep_msg_type);
        }
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
            let mut svc = ZmqService::new(sender, ::std::time::Duration::from_secs(10));

            svc.send_to(Default::default(), Default::default(), Default::default())
                .unwrap();
            svc.broadcast(Default::default(), Default::default())
                .unwrap();
            svc.initialize_block(Some(Default::default())).unwrap();
            svc.finalize_block(Default::default()).unwrap();
            svc.cancel_block().unwrap();
            svc.commit_block(Default::default()).unwrap();
            svc.hold_block(Default::default()).unwrap();
            svc.drop_block(Default::default()).unwrap();
            svc.fail_block(Default::default()).unwrap();
            svc.get_block(Default::default()).unwrap();
            svc.get_setting(Default::default(), Default::default())
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
            ConsensusCommitBlockResponse::new(),
            ConsensusCommitBlockResponse_Status::OK,
            Message_MessageType::CONSENSUS_COMMIT_BLOCK_RESPONSE,
            ConsensusCommitBlockRequest,
            Message_MessageType::CONSENSUS_COMMIT_BLOCK_REQUEST
        );

        service_test!(
            &socket,
            ConsensusHoldBlockResponse::new(),
            ConsensusHoldBlockResponse_Status::OK,
            Message_MessageType::CONSENSUS_HOLD_BLOCK_RESPONSE,
            ConsensusHoldBlockRequest,
            Message_MessageType::CONSENSUS_HOLD_BLOCK_REQUEST
        );

        service_test!(
            &socket,
            ConsensusDropBlockResponse::new(),
            ConsensusDropBlockResponse_Status::OK,
            Message_MessageType::CONSENSUS_DROP_BLOCK_RESPONSE,
            ConsensusDropBlockRequest,
            Message_MessageType::CONSENSUS_DROP_BLOCK_REQUEST
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
            ConsensusBlockGetResponse::new(),
            ConsensusBlockGetResponse_Status::OK,
            Message_MessageType::CONSENSUS_BLOCK_GET_RESPONSE,
            ConsensusBlockGetRequest,
            Message_MessageType::CONSENSUS_BLOCK_GET_REQUEST
        );

        service_test!(
            &socket,
            ConsensusSettingGetResponse::new(),
            ConsensusSettingGetResponse_Status::OK,
            Message_MessageType::CONSENSUS_SETTING_GET_RESPONSE,
            ConsensusSettingGetRequest,
            Message_MessageType::CONSENSUS_SETTING_GET_REQUEST
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

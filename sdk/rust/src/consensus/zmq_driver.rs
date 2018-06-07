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

use consensus::engine::*;
use consensus::zmq_service::ZmqService;

use messaging::stream::MessageConnection;
use messaging::stream::MessageSender;
use messaging::stream::ReceiveError;
use messaging::stream::SendError;
use messaging::zmq_stream::ZmqMessageConnection;

use messages::consensus::*;
use messages::validator::{Message, Message_MessageType};

use std::sync::{mpsc::{channel, RecvTimeoutError, Sender},
                Arc};

const REGISTER_TIMEOUT: u64 = 300;
const SERVICE_TIMEOUT: u64 = 300;

/// Generates a random correlation id for use in Message
fn generate_correlation_id() -> String {
    const LENGTH: usize = 16;
    rand::thread_rng().gen_ascii_chars().take(LENGTH).collect()
}

pub struct ZmqDriver {
    engine: Arc<Box<Engine>>,
    exit: Exit,
}

impl ZmqDriver {
    pub fn new(engine: Box<Engine>) -> Self {
        ZmqDriver {
            engine: Arc::new(engine),
            exit: Exit::new(),
        }
    }

    pub fn start(&self, endpoint: &str) -> Result<(), Error> {
        let validator_connection = ZmqMessageConnection::new(endpoint);
        let (mut validator_sender, validator_receiver) = validator_connection.create();

        let (chain_head, peers) = register(
            &mut validator_sender,
            ::std::time::Duration::from_secs(REGISTER_TIMEOUT),
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
                    ::std::time::Duration::from_secs(SERVICE_TIMEOUT),
                    engine.name(),
                    engine.version(),
                )),
                chain_head,
                peers,
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

    pub fn stop(&self) {
        self.exit.set();
    }
}

pub fn register(
    sender: &mut MessageSender,
    timeout: ::std::time::Duration,
    name: String,
    version: String,
) -> Result<(Block, Vec<PeerInfo>), Error> {
    let mut request = ConsensusRegisterRequest::new();
    request.set_name(name);
    request.set_version(version);
    let request = request.write_to_bytes()?;

    let mut msg = sender
        .send(
            Message_MessageType::CONSENSUS_REGISTER_REQUEST,
            &generate_correlation_id(),
            &request,
        )?
        .get_timeout(timeout)?;

    let ret: Result<(Block, Vec<PeerInfo>), Error>;

    // Keep trying to register until the response is something other
    // than NOT_READY.
    loop {
        match msg.get_message_type() {
            Message_MessageType::CONSENSUS_REGISTER_RESPONSE => {
                let mut response: ConsensusRegisterResponse =
                    protobuf::parse_from_bytes(msg.get_content())?;

                match response.get_status() {
                    ConsensusRegisterResponse_Status::OK => {
                        ret = Ok((
                            response.take_chain_head().into(),
                            response
                                .take_peers()
                                .into_iter()
                                .map(|info| info.into())
                                .collect(),
                        ));

                        break;
                    }
                    ConsensusRegisterResponse_Status::NOT_READY => {
                        msg = sender
                            .send(
                                Message_MessageType::CONSENSUS_REGISTER_REQUEST,
                                &generate_correlation_id(),
                                &request,
                            )?
                            .get_timeout(timeout)?;

                        continue;
                    }
                    status => {
                        ret = Err(Error::ReceiveError(format!(
                            "Registration failed with status {:?}",
                            status
                        )));

                        break;
                    }
                };
            }
            unexpected => {
                ret = Err(Error::ReceiveError(format!(
                    "Received unexpected message type: {:?}",
                    unexpected
                )));

                break;
            }
        }
    }

    ret
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
            Update::PeerMessage(
                request.take_message().into(),
                request.take_sender_id().into(),
            )
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

impl From<ConsensusBlock> for Block {
    fn from(mut c_block: ConsensusBlock) -> Block {
        Block {
            block_id: c_block.take_block_id().into(),
            previous_id: c_block.take_previous_id().into(),
            signer_id: c_block.take_signer_id().into(),
            block_num: c_block.get_block_num(),
            payload: c_block.take_payload(),
            summary: c_block.take_summary(),
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
}

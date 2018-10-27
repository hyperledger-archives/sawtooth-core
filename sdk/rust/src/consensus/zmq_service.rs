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
use protobuf::Message as ProtobufMessage;
use rand;
use rand::Rng;

use consensus::engine::*;
use consensus::service::Service;

use messaging::stream::MessageSender;
use messaging::zmq_stream::ZmqMessageSender;

use messages::consensus::*;
use messages::validator::Message_MessageType;

use std::collections::HashMap;
use std::time::Duration;

/// Generates a random correlation id for use in Message
fn generate_correlation_id() -> String {
    const LENGTH: usize = 16;
    rand::thread_rng().gen_ascii_chars().take(LENGTH).collect()
}

pub struct ZmqService {
    sender: ZmqMessageSender,
    timeout: Duration,
}

impl ZmqService {
    pub fn new(sender: ZmqMessageSender, timeout: Duration) -> Self {
        ZmqService { sender, timeout }
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
        let mut future = self
            .sender
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
        let mut request = ConsensusSendToRequest::new();
        request.set_content(payload);
        request.set_message_type(message_type.into());
        request.set_receiver_id((*peer).clone().into());

        let response: ConsensusSendToResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_SEND_TO_REQUEST,
            Message_MessageType::CONSENSUS_SEND_TO_RESPONSE,
        )?;

        check_ok!(response, ConsensusSendToResponse_Status::OK)
    }

    fn broadcast(&mut self, message_type: &str, payload: Vec<u8>) -> Result<(), Error> {
        let mut request = ConsensusBroadcastRequest::new();
        request.set_content(payload);
        request.set_message_type(message_type.into());

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

    fn summarize_block(&mut self) -> Result<Vec<u8>, Error> {
        let request = ConsensusSummarizeBlockRequest::new();

        let mut response: ConsensusSummarizeBlockResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_SUMMARIZE_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_SUMMARIZE_BLOCK_RESPONSE,
        )?;

        match response.get_status() {
            ConsensusSummarizeBlockResponse_Status::INVALID_STATE => Err(Error::InvalidState(
                "Cannot summarize block in current state".into(),
            )),
            ConsensusSummarizeBlockResponse_Status::BLOCK_NOT_READY => Err(Error::BlockNotReady),
            _ => check_ok!(response, ConsensusSummarizeBlockResponse_Status::OK),
        }?;

        Ok(response.take_summary())
    }

    fn finalize_block(&mut self, data: Vec<u8>) -> Result<BlockId, Error> {
        let mut request = ConsensusFinalizeBlockRequest::new();
        request.set_data(data);

        let mut response: ConsensusFinalizeBlockResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_FINALIZE_BLOCK_REQUEST,
            Message_MessageType::CONSENSUS_FINALIZE_BLOCK_RESPONSE,
        )?;

        match response.get_status() {
            ConsensusFinalizeBlockResponse_Status::INVALID_STATE => Err(Error::InvalidState(
                "Cannot finalize block in current state".into(),
            )),
            ConsensusFinalizeBlockResponse_Status::BLOCK_NOT_READY => Err(Error::BlockNotReady),
            _ => check_ok!(response, ConsensusFinalizeBlockResponse_Status::OK),
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
        let mut request = ConsensusCheckBlocksRequest::new();
        request.set_block_ids(protobuf::RepeatedField::from_vec(
            priority.into_iter().map(Vec::from).collect(),
        ));

        let response: ConsensusCheckBlocksResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_CHECK_BLOCKS_REQUEST,
            Message_MessageType::CONSENSUS_CHECK_BLOCKS_RESPONSE,
        )?;

        if response.get_status() == ConsensusCheckBlocksResponse_Status::UNKNOWN_BLOCK {
            Err(Error::UnknownBlock("Block not found".into()))
        } else {
            check_ok!(response, ConsensusCheckBlocksResponse_Status::OK)
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

    fn get_blocks(&mut self, block_ids: Vec<BlockId>) -> Result<HashMap<BlockId, Block>, Error> {
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
            .map(|block| (BlockId::from(block.block_id.clone()), Block::from(block)))
            .collect())
    }

    fn get_chain_head(&mut self) -> Result<Block, Error> {
        let request = ConsensusChainHeadGetRequest::new();

        let mut response: ConsensusChainHeadGetResponse = self.rpc(
            &request,
            Message_MessageType::CONSENSUS_CHAIN_HEAD_GET_REQUEST,
            Message_MessageType::CONSENSUS_CHAIN_HEAD_GET_RESPONSE,
        )?;

        if response.get_status() == ConsensusChainHeadGetResponse_Status::NO_CHAIN_HEAD {
            Err(Error::NoChainHead)
        } else {
            check_ok!(response, ConsensusChainHeadGetResponse_Status::OK)
        }?;

        Ok(Block::from(response.take_block()))
    }

    fn get_settings(
        &mut self,
        block_id: BlockId,
        keys: Vec<String>,
    ) -> Result<HashMap<String, String>, Error> {
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
            .map(|mut entry| (entry.take_key(), entry.take_value()))
            .collect())
    }

    fn get_state(
        &mut self,
        block_id: BlockId,
        addresses: Vec<String>,
    ) -> Result<HashMap<String, Vec<u8>>, Error> {
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
            .map(|mut entry| (entry.take_address(), entry.take_data()))
            .collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use messages::validator::Message;
    use messaging::stream::MessageConnection;
    use messaging::zmq_stream::ZmqMessageConnection;
    use std::default::Default;
    use std::thread;
    use zmq;

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

        let svc_thread = thread::spawn(move || {
            let connection = ZmqMessageConnection::new(&addr);
            let (sender, _) = connection.create();
            let mut svc = ZmqService::new(sender, Duration::from_secs(10));

            svc.send_to(&Default::default(), Default::default(), Default::default())
                .unwrap();
            svc.broadcast(Default::default(), Default::default())
                .unwrap();

            svc.initialize_block(Some(Default::default())).unwrap();
            svc.summarize_block().unwrap();
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
            svc.get_chain_head().unwrap();
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
            ConsensusSummarizeBlockResponse::new(),
            ConsensusSummarizeBlockResponse_Status::OK,
            Message_MessageType::CONSENSUS_SUMMARIZE_BLOCK_RESPONSE,
            ConsensusSummarizeBlockRequest,
            Message_MessageType::CONSENSUS_SUMMARIZE_BLOCK_REQUEST
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
            ConsensusCheckBlocksResponse::new(),
            ConsensusCheckBlocksResponse_Status::OK,
            Message_MessageType::CONSENSUS_CHECK_BLOCKS_RESPONSE,
            ConsensusCheckBlocksRequest,
            Message_MessageType::CONSENSUS_CHECK_BLOCKS_REQUEST
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

        service_test!(
            &socket,
            ConsensusChainHeadGetResponse::new(),
            ConsensusChainHeadGetResponse_Status::OK,
            Message_MessageType::CONSENSUS_CHAIN_HEAD_GET_RESPONSE,
            ConsensusChainHeadGetRequest,
            Message_MessageType::CONSENSUS_CHAIN_HEAD_GET_REQUEST
        );

        svc_thread.join().unwrap();
    }
}

/*
 * Copyright 2018 Cargill Incorporated
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

use block::Block;

use crypto::digest::Digest;
use crypto::sha2::Sha256;

use proto::validator::Message_MessageType as MessageType;
use proto::consensus::{
    ConsensusBlock,
    ConsensusPeerInfo,
    ConsensusPeerMessage,
    ConsensusNotifyBlockNew,
    ConsensusNotifyPeerConnected,
    ConsensusNotifyPeerDisconnected,
    ConsensusNotifyPeerMessage,
    ConsensusNotifyBlockValid,
    ConsensusNotifyBlockInvalid,
    ConsensusNotifyBlockCommit,
    ConsensusNotifyBatchNew,
    ConsensusNotifyBatchInvalid,
};

use protobuf::{RepeatedField, Message};

pub trait ConsensusNotifier: Send + Sync {
    fn notify_peer_connected(&self, peer_id: &str);
    fn notify_peer_disconnected(&self, peer_id: &str);
    fn notify_peer_message(&self, message: ConsensusPeerMessage, sender_id: &str);

    fn notify_block_new(&self, block: &Block);
    fn notify_block_valid(&self, block_id: &str);
    fn notify_block_invalid(&self, block_id: &str);
    fn notify_block_commit(&self, block_id: &str);

    fn notify_batch_new(&self, batch_id: &str);
    fn notify_batch_invalid(&self, batch_id: &str);
}

#[derive(Debug)]
pub struct NotifierServiceError(pub String);

pub trait NotifierService: Sync + Send {
    fn notify<T: Message>(&self, message_type: MessageType, message: T) -> Result<(), NotifierServiceError>;
}

impl<T: NotifierService> ConsensusNotifier for T {
    fn notify_peer_connected(&self, peer_id: &str) {
        let mut peer_info = ConsensusPeerInfo::new();
        peer_info.set_peer_id(peer_id.as_bytes().into());

        let mut notification = ConsensusNotifyPeerConnected::new();
        notification.set_peer_info(peer_info);

        self.notify(MessageType::CONSENSUS_NOTIFY_PEER_CONNECTED, notification)
            .expect("Failed to send peer connected notification");
    }

    fn notify_peer_disconnected(&self, peer_id: &str) {
        let mut notification = ConsensusNotifyPeerDisconnected::new();
        notification.set_peer_id(peer_id.as_bytes().into());

        self.notify(MessageType::CONSENSUS_NOTIFY_PEER_DISCONNECTED, notification)
            .expect("Failed to send peer disconnected notification");
    }

    fn notify_peer_message(&self, message: ConsensusPeerMessage, sender_id: &str) {
        let mut notification = ConsensusNotifyPeerMessage::new();
        notification.set_message(message);
        notification.set_sender_id(sender_id.as_bytes().into());

        self.notify(MessageType::CONSENSUS_NOTIFY_PEER_MESSAGE, notification)
            .expect("Failed to send peer message notification");
    }


    fn notify_block_new(&self, block: &Block) {
        let summary = summarize(block);

        let mut consensus_block = ConsensusBlock::new();
        consensus_block.set_block_id(block.header_signature.as_bytes().into());
        consensus_block.set_previous_id(block.previous_block_id.as_bytes().into());
        consensus_block.set_signer_id(block.signer_public_key.as_bytes().into());
        consensus_block.set_block_num(block.block_num);
        consensus_block.set_payload(block.consensus.clone());
        consensus_block.set_summary(summary);
        consensus_block.set_batches(
            RepeatedField::from_vec(
                block
                    .batch_ids
                    .iter()
                    .map(|id| id.as_bytes().into())
                    .collect()
            )
        );

        let mut notification = ConsensusNotifyBlockNew::new();
        notification.set_block(consensus_block);

        self.notify(MessageType::CONSENSUS_NOTIFY_BLOCK_NEW, notification)
            .expect("Failed to send block new notification");
    }

    fn notify_block_valid(&self, block_id: &str) {
        let mut notification = ConsensusNotifyBlockValid::new();
        notification.set_block_id(block_id.as_bytes().into());

        self.notify(MessageType::CONSENSUS_NOTIFY_BLOCK_VALID, notification)
            .expect("Failed to send block valid notification");
    }

    fn notify_block_invalid(&self, block_id: &str) {
        let mut notification = ConsensusNotifyBlockInvalid::new();
        notification.set_block_id(block_id.as_bytes().into());

        self.notify(MessageType::CONSENSUS_NOTIFY_BLOCK_INVALID, notification)
            .expect("Failed to send block invalid notification");
    }

    fn notify_block_commit(&self, block_id: &str) {
        let mut notification = ConsensusNotifyBlockCommit::new();
        notification.set_block_id(block_id.as_bytes().into());

        self.notify(MessageType::CONSENSUS_NOTIFY_BLOCK_COMMIT, notification)
            .expect("Failed to send block commit notification");
    }


    fn notify_batch_new(&self, batch_id: &str) {
        let mut notification = ConsensusNotifyBatchNew::new();
        notification.set_batch_id(batch_id.as_bytes().into());

        self.notify(MessageType::CONSENSUS_NOTIFY_BATCH_NEW, notification)
            .expect("Failed to send batch new notification");
    }

    fn notify_batch_invalid(&self, batch_id: &str) {
        let mut notification = ConsensusNotifyBatchInvalid::new();
        notification.set_batch_id(batch_id.as_bytes().into());

        self.notify(MessageType::CONSENSUS_NOTIFY_BATCH_INVALID, notification)
            .expect("Failed to send batch invalid notification");
    }

}

fn summarize(block: &Block) -> Vec<u8> {
    let mut hasher = Sha256::new();
    for batch in &block.batches {
        hasher.input_str(&batch.header_signature);
    }

    let mut digest = Vec::with_capacity(hasher.output_bytes());
    hasher.result(&mut digest);

    digest
}

// pub struct BackgroundNotifier<T: ConsensusNotifier> {
//     notifier: T,
// }

// impl<T: ConsensusNotifier> ConsensusNotifier for Background<T> {
//
// }

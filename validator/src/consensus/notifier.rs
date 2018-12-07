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

use std::sync::mpsc::{channel, Sender};
use std::sync::{Arc, Mutex};
use std::thread;

use block::Block;

use hashlib::sha256_digest_strs;
use hex;
use protobuf::{Message, RepeatedField};

use proto::consensus::{
    ConsensusBlock, ConsensusNotifyBlockCommit, ConsensusNotifyBlockInvalid,
    ConsensusNotifyBlockNew, ConsensusNotifyBlockValid, ConsensusNotifyEngineActivated,
    ConsensusNotifyEngineDeactivated, ConsensusNotifyPeerConnected,
    ConsensusNotifyPeerDisconnected, ConsensusNotifyPeerMessage, ConsensusPeerInfo,
    ConsensusPeerMessage,
};
use proto::validator::Message_MessageType as MessageType;

pub trait ConsensusNotifier: Send + Sync {
    fn notify_peer_connected(&self, peer_id: &str);
    fn notify_peer_disconnected(&self, peer_id: &str);
    fn notify_peer_message(&self, message: ConsensusPeerMessage, sender_id: &[u8]);

    fn notify_block_new(&self, block: &Block);
    fn notify_block_valid(&self, block_id: &str);
    fn notify_block_invalid(&self, block_id: &str);
    fn notify_block_commit(&self, block_id: &str);
    fn notify_engine_activated(&self, block: &Block);
    fn notify_engine_deactivated(&self, connection_id: String);
}

#[derive(Debug)]
pub struct NotifierServiceError(pub String);

pub trait NotifierService: Sync + Send {
    fn notify<T: Message>(
        &self,
        message_type: MessageType,
        message: T,
    ) -> Result<(), NotifierServiceError>;

    fn notify_id<T: Message>(
        &self,
        message_type: MessageType,
        message: T,
        connection_id: String,
    ) -> Result<(), NotifierServiceError>;

    fn get_peers_public_keys(&self) -> Result<Vec<String>, NotifierServiceError>;

    fn get_public_key(&self) -> Result<String, NotifierServiceError>;
}

impl<T: NotifierService> ConsensusNotifier for T {
    fn notify_peer_connected(&self, peer_id: &str) {
        let mut peer_info = ConsensusPeerInfo::new();
        peer_info.set_peer_id(from_hex(peer_id, "peer_id"));

        let mut notification = ConsensusNotifyPeerConnected::new();
        notification.set_peer_info(peer_info);

        self.notify(MessageType::CONSENSUS_NOTIFY_PEER_CONNECTED, notification)
            .expect("Failed to send peer connected notification");
    }

    fn notify_peer_disconnected(&self, peer_id: &str) {
        let mut notification = ConsensusNotifyPeerDisconnected::new();
        notification.set_peer_id(from_hex(peer_id, "peer_id"));

        self.notify(
            MessageType::CONSENSUS_NOTIFY_PEER_DISCONNECTED,
            notification,
        )
        .expect("Failed to send peer disconnected notification");
    }

    fn notify_peer_message(&self, message: ConsensusPeerMessage, sender_id: &[u8]) {
        let mut notification = ConsensusNotifyPeerMessage::new();
        notification.set_message(message);
        notification.set_sender_id(sender_id.into());

        self.notify(MessageType::CONSENSUS_NOTIFY_PEER_MESSAGE, notification)
            .expect("Failed to send peer message notification");
    }

    fn notify_block_new(&self, block: &Block) {
        let consensus_block = get_consensus_block(block);

        let mut notification = ConsensusNotifyBlockNew::new();
        notification.set_block(consensus_block);

        self.notify(MessageType::CONSENSUS_NOTIFY_BLOCK_NEW, notification)
            .expect("Failed to send block new notification");
    }

    fn notify_block_valid(&self, block_id: &str) {
        let mut notification = ConsensusNotifyBlockValid::new();
        notification.set_block_id(from_hex(block_id, "block_id"));

        self.notify(MessageType::CONSENSUS_NOTIFY_BLOCK_VALID, notification)
            .expect("Failed to send block valid notification");
    }

    fn notify_block_invalid(&self, block_id: &str) {
        let mut notification = ConsensusNotifyBlockInvalid::new();
        notification.set_block_id(from_hex(block_id, "block_id"));

        self.notify(MessageType::CONSENSUS_NOTIFY_BLOCK_INVALID, notification)
            .expect("Failed to send block invalid notification");
    }

    fn notify_block_commit(&self, block_id: &str) {
        let mut notification = ConsensusNotifyBlockCommit::new();
        notification.set_block_id(from_hex(block_id, "block_id"));

        self.notify(MessageType::CONSENSUS_NOTIFY_BLOCK_COMMIT, notification)
            .expect("Failed to send block commit notification");
    }

    fn notify_engine_activated(&self, block: &Block) {
        let chain_head = get_consensus_block(block);

        let peers = RepeatedField::from_vec(
            self.get_peers_public_keys()
                .expect("Failed to get list of peers")
                .iter()
                .map(|peer_id| {
                    let mut peer_info = ConsensusPeerInfo::new();
                    peer_info.set_peer_id(from_hex(peer_id, "peer_id"));
                    peer_info
                })
                .collect(),
        );

        let mut local_peer_info = ConsensusPeerInfo::new();
        local_peer_info.set_peer_id(from_hex(
            self.get_public_key().expect("Failed to get public key"),
            "pub_key",
        ));

        let mut notification = ConsensusNotifyEngineActivated::new();
        notification.set_chain_head(chain_head);
        notification.set_peers(peers);
        notification.set_local_peer_info(local_peer_info);

        self.notify(MessageType::CONSENSUS_NOTIFY_ENGINE_ACTIVATED, notification)
            .expect("Failed to send engine activation notification");
    }

    fn notify_engine_deactivated(&self, connection_id: String) {
        let notification = ConsensusNotifyEngineDeactivated::new();

        self.notify_id(
            MessageType::CONSENSUS_NOTIFY_ENGINE_DEACTIVATED,
            notification,
            connection_id,
        )
        .expect("Failed to send engine deactivation notification");
    }
}

fn get_consensus_block(block: &Block) -> ConsensusBlock {
    let batch_ids: Vec<&str> = block
        .batches
        .iter()
        .map(|batch| batch.header_signature.as_str())
        .collect();

    let summary = sha256_digest_strs(batch_ids.as_slice());

    let mut consensus_block = ConsensusBlock::new();
    consensus_block.set_block_id(from_hex(&block.header_signature, "block.header_signature"));
    consensus_block.set_previous_id(from_hex(
        &block.previous_block_id,
        "block.previous_block_id",
    ));
    consensus_block.set_signer_id(from_hex(
        &block.signer_public_key,
        "block.signer_public_key",
    ));
    consensus_block.set_block_num(block.block_num);
    consensus_block.set_payload(block.consensus.clone());
    consensus_block.set_summary(summary);

    consensus_block
}

fn from_hex<T: AsRef<str>>(hex_string: T, id_name: &str) -> Vec<u8> {
    match hex::decode(hex_string.as_ref()) {
        Ok(d) => d,
        Err(err) => panic!("{} is invalid hex: {:?}", id_name, err),
    }
}

#[derive(Debug)]
enum ConsensusNotification {
    PeerConnected(String),
    PeerDisconnected(String),
    PeerMessage((ConsensusPeerMessage, Vec<u8>)),
    BlockNew(Block),
    BlockValid(String),
    BlockInvalid(String),
    BlockCommit(String),
    EngineActivated(Block),
    EngineDeactivated(String),
}

#[derive(Clone)]
pub struct BackgroundConsensusNotifier {
    tx: Arc<Mutex<Sender<ConsensusNotification>>>,
}

impl BackgroundConsensusNotifier {
    pub fn new<T: ConsensusNotifier + 'static>(notifier: T) -> Self {
        let (tx, rx) = channel();
        let thread_builder = thread::Builder::new().name("BackgroundConsensusNotifier".into());
        thread_builder
            .spawn(move || loop {
                if let Ok(notification) = rx.recv() {
                    handle_notification(&notifier, notification);
                } else {
                    break;
                }
            })
            .expect("Failed to spawn BackgroundConsensusNotifier thread");
        BackgroundConsensusNotifier {
            tx: Arc::new(Mutex::new(tx)),
        }
    }

    fn send_notification(&self, notification: ConsensusNotification) {
        self.tx
            .lock()
            .expect("Lock poisoned")
            .send(notification)
            .expect("Failed to send notification to background thread");
    }
}

impl ConsensusNotifier for BackgroundConsensusNotifier {
    fn notify_peer_connected(&self, peer_id: &str) {
        self.send_notification(ConsensusNotification::PeerConnected(peer_id.into()))
    }

    fn notify_peer_disconnected(&self, peer_id: &str) {
        self.send_notification(ConsensusNotification::PeerDisconnected(peer_id.into()))
    }

    fn notify_peer_message(&self, message: ConsensusPeerMessage, sender_id: &[u8]) {
        self.send_notification(ConsensusNotification::PeerMessage((
            message,
            sender_id.into(),
        )))
    }

    fn notify_block_new(&self, block: &Block) {
        self.send_notification(ConsensusNotification::BlockNew(block.clone()))
    }

    fn notify_block_valid(&self, block_id: &str) {
        self.send_notification(ConsensusNotification::BlockValid(block_id.into()))
    }

    fn notify_block_invalid(&self, block_id: &str) {
        self.send_notification(ConsensusNotification::BlockInvalid(block_id.into()))
    }

    fn notify_block_commit(&self, block_id: &str) {
        self.send_notification(ConsensusNotification::BlockCommit(block_id.into()))
    }

    fn notify_engine_activated(&self, block: &Block) {
        self.send_notification(ConsensusNotification::EngineActivated(block.clone()))
    }

    fn notify_engine_deactivated(&self, connection_id: String) {
        self.send_notification(ConsensusNotification::EngineDeactivated(connection_id))
    }
}

fn handle_notification<T: ConsensusNotifier>(notifier: &T, notification: ConsensusNotification) {
    match notification {
        ConsensusNotification::PeerConnected(peer_id) => notifier.notify_peer_connected(&peer_id),
        ConsensusNotification::PeerDisconnected(peer_id) => {
            notifier.notify_peer_disconnected(&peer_id)
        }
        ConsensusNotification::PeerMessage((msg, sender_id)) => {
            notifier.notify_peer_message(msg, &sender_id)
        }
        ConsensusNotification::BlockNew(block) => notifier.notify_block_new(&block),
        ConsensusNotification::BlockValid(block_id) => notifier.notify_block_valid(&block_id),
        ConsensusNotification::BlockInvalid(block_id) => notifier.notify_block_invalid(&block_id),
        ConsensusNotification::BlockCommit(block_id) => notifier.notify_block_commit(&block_id),
        ConsensusNotification::EngineActivated(block) => notifier.notify_engine_activated(&block),
        ConsensusNotification::EngineDeactivated(connection_id) => {
            notifier.notify_engine_deactivated(connection_id)
        }
    }
}

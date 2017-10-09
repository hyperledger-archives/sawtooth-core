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
 * -----------------------------------------------------------------------------
 */

extern crate zmq;
extern crate uuid;

use std::sync::{Arc, Mutex};
use std::sync::mpsc::{Receiver, SyncSender, Sender,
                      sync_channel, channel,
                      RecvTimeoutError};
use std::thread;
use std::time::Duration;
use std::collections::HashMap;

use protobuf;
use messages::validator::Message;
use messages::validator::Message_MessageType;

use super::stream::*;

/// A MessageConnection over ZMQ sockets
pub struct ZmqMessageConnection {
    address: String,
    context: zmq::Context,
}

const CHANNEL_BUFFER_SIZE: usize = 128;

impl ZmqMessageConnection {
    /// Create a new ZmqMessageConnection
    pub fn new(address: &str) -> Self {
        ZmqMessageConnection {
            address: String::from(address),
            context: zmq::Context::new(),
        }
    }
}

impl MessageConnection<ZmqMessageSender> for ZmqMessageConnection {
    fn create(&self) -> (ZmqMessageSender, MessageReceiver) {
        // Create the channel for request messages (i.e. non-reply messages)
        let (request_tx, request_rx) = sync_channel(CHANNEL_BUFFER_SIZE);
        let router = InboundRouter::new(request_tx);
        let mut sender = ZmqMessageSender::new(
            self.context.clone(), self.address.clone(), router);

        sender.start();

        (sender, request_rx)
    }
}


#[derive(Clone)]
pub struct ZmqMessageSender {
    context: zmq::Context,
    address: String,
    inbound_router: InboundRouter,
    outbound_sender: Option<SyncSender<Option<Message>>>,
}

impl ZmqMessageSender {

    fn new(ctx: zmq::Context, address: String, router: InboundRouter) -> Self {
        ZmqMessageSender {
           context: ctx,
           address: address,
           inbound_router: router,
           outbound_sender: None
        }
    }

    /// Start the message stream instance
    fn start(&mut self) {
        let (outbound_send, outbound_recv) = sync_channel(CHANNEL_BUFFER_SIZE);
        self.outbound_sender = Some(outbound_send);

        let ctx = self.context.clone();
        let address = self.address.clone();
        let inbound_router = self.inbound_router.clone();
        thread::spawn(move || {
            let mut inner_stream = SendReceiveStream::new(
                ctx,
                &address,
                outbound_recv,
                inbound_router,
            );
            inner_stream.run();
        });
    }
}


impl MessageSender for ZmqMessageSender {
    fn send(&mut self, destination: Message_MessageType, correlation_id: &str,
            contents: &[u8])
        -> Result<MessageFuture, SendError>
    {
        if let Some(ref sender) = self.outbound_sender {
            let mut msg = Message::new();

            msg.set_message_type(destination);
            msg.set_correlation_id(String::from(correlation_id));
            msg.set_content(Vec::from(contents));

            let future = MessageFuture::new(self.inbound_router.expect_reply(
                    String::from(correlation_id)));

            sender.send(Some(msg)).unwrap();

            Ok(future)
        } else {
            Err(SendError::DisconnectedError)
        }
    }

    fn reply(&mut self, destination: Message_MessageType, correlation_id: &str,
             contents: &[u8])
        -> Result<(), SendError>
    {
        if let Some(ref sender) = self.outbound_sender {
            let mut msg = Message::new();
            msg.set_message_type(destination);
            msg.set_correlation_id(String::from(correlation_id));
            msg.set_content(Vec::from(contents));

            match sender.send(Some(msg)) {
                Ok(_) => Ok(()),
                Err(_) => Err(SendError::UnknownError)
            }
        } else {
            Err(SendError::DisconnectedError)
        }
    }

    fn close(&mut self) {
        if let Some(ref sender) = self.outbound_sender.take() {
            sender.send(None).unwrap();
        }
    }
}

#[derive(Clone)]
struct InboundRouter {
    inbound_tx: SyncSender<MessageResult>,
    expected_replies: Arc<Mutex<HashMap<String, Sender<MessageResult>>>>,
}

impl InboundRouter {
    fn new(inbound_tx: SyncSender<MessageResult>) -> Self {
        InboundRouter {
            inbound_tx: inbound_tx,
            expected_replies: Arc::new(Mutex::new(HashMap::new()))
        }
    }

    fn route(&mut self, message: Message) {
        let mut expected_replies = self.expected_replies.lock().unwrap();
        match expected_replies.remove(
            message.get_correlation_id())
        {
            Some(sender) => sender.send(Ok(message)).unwrap(),
            None => self.inbound_tx.send(Ok(message)).unwrap()
        }
    }

    fn expect_reply(&mut self, correlation_id: String) -> Receiver<MessageResult> {
        let (expect_tx, expect_rx) = channel();
        let mut expected_replies = self.expected_replies.lock().unwrap();
        expected_replies.insert(correlation_id, expect_tx);

        expect_rx
    }
}

/// Internal stream, guarding  a zmq socket.
struct SendReceiveStream {
    address: String,
    socket: zmq::Socket,
    outbound_recv: Receiver<Option<Message>>,
    inbound_router: InboundRouter
}

const POLL_TIMEOUT: i64 = 10;

impl SendReceiveStream {
    fn new(context: zmq::Context, address: &str,
           outbound_recv: Receiver<Option<Message>>,
           inbound_router: InboundRouter)
        -> Self
    {
        let socket = context.socket(zmq::DEALER).unwrap();

        let identity = uuid::Uuid::new(uuid::UuidVersion::Random).unwrap();
        socket.set_identity(identity.as_bytes()).unwrap();

        SendReceiveStream {
            address: String::from(address),
            socket: socket,

            outbound_recv: outbound_recv,
            inbound_router: inbound_router,
        }
    }

    fn run(&mut self) {
        self.socket.connect(&self.address).unwrap();
        loop {
            let mut poll_items = [self.socket.as_poll_item(zmq::POLLIN)];
            zmq::poll(&mut poll_items, POLL_TIMEOUT).unwrap();
            if poll_items[0].is_readable() {
                trace!("Readable!");
                let mut received_parts = self.socket.recv_multipart(0).unwrap();

                // Grab the last part, which should contain our message
                if let Some(received_bytes) = received_parts.pop() {
                    trace!("Received {} bytes", received_bytes.len());
                    if received_bytes.len() != 0 {
                        let message = protobuf::parse_from_bytes(&received_bytes).unwrap();
                        self.inbound_router.route(message);
                    }
                } else {
                    debug!("Empty frame received.");
                }
            }

            match self.outbound_recv.recv_timeout(
                Duration::from_millis(POLL_TIMEOUT as u64))
            {
                Ok(Some(msg)) => {
                    let message_bytes = protobuf::Message::write_to_bytes(&msg).unwrap();
                    trace!("Sending {} bytes", message_bytes.len());
                    self.socket.send(&message_bytes, 0).unwrap();
                }
                Ok(None) => {
                    trace!("Shutdown Signal Received");
                    break;
                }
                Err(RecvTimeoutError::Disconnected) => {
                    debug!("Disconnected outbound channel");
                    break
                }
                _ => continue
            }
        }

        debug!("Exited stream");
        self.socket.disconnect(&self.address).unwrap();
    }
}

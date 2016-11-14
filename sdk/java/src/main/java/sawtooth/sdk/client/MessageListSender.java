/* Copyright 2016 Intel Corporation
 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
------------------------------------------------------------------------------*/

package sawtooth.sdk.client;

import io.grpc.ClientCall;
import sawtooth.sdk.protobuf.Message;
import sawtooth.sdk.protobuf.MessageList;

import java.util.ArrayList;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.logging.Logger;


class MessageListSender implements Runnable {
  private ClientCall<MessageList, MessageList> call;
  private LinkedBlockingQueue<Message> queue;

  private final Logger logger = Logger.getLogger(MessageListSender.class.getName());
  private boolean stop;

  MessageListSender(LinkedBlockingQueue<Message> sendQueue,
                    ClientCall<MessageList, MessageList> call) {
    super();
    this.queue = sendQueue;
    this.call = call;
    this.stop = false;
  }


  @Override
  public void run() {
    while (true) {
      if (this.stop && this.queue.isEmpty()) {
        logger.info("Has stopped!");
        break;
      }

      ArrayList<Message> messageArrayList = new ArrayList<Message>();
      try {
        messageArrayList.add(this.queue.take());
      } catch (InterruptedException ie) {
        logger.info(ie.toString());
        break;
      }
      this.queue.drainTo(messageArrayList);

      MessageList messageList = MessageList.newBuilder().addAllMessages(messageArrayList).build();
      this.call.sendMessage(messageList);

    }
  }

  public void stopRunning() {
    this.stop = true;
  }


}

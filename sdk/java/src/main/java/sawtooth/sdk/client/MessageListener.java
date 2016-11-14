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

import com.google.common.util.concurrent.SettableFuture;
import com.google.protobuf.ByteString;

import io.grpc.ClientCall;
import sawtooth.sdk.protobuf.Message;
import sawtooth.sdk.protobuf.MessageList;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;


class MessageListener extends ClientCall.Listener<MessageList> {

  private ConcurrentHashMap<String, SettableFuture<ByteString>> futureHashMap;
  private LinkedBlockingQueue<Message> receiveQueue;

  MessageListener(ConcurrentHashMap<String, SettableFuture<ByteString>> futures,
                  LinkedBlockingQueue<Message> receiveQueue) {
    super();
    this.futureHashMap = futures;
    this.receiveQueue = receiveQueue;
  }


  @Override
  public void onMessage(MessageList messageList) {
    for (Message message : messageList.getMessagesList()) {
      String correlationId = message.getCorrelationId();

      if (this.futureHashMap.containsKey(correlationId)) {
        SettableFuture<ByteString> future = this.futureHashMap.get(correlationId);
        future.set(message.getContent());
        this.futureHashMap.put(correlationId, future);
      } else {
        this.receiveQueue.add(message);
      }
    }
  }

}

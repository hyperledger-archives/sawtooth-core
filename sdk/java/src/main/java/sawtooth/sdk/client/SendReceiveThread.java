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

import com.google.protobuf.InvalidProtocolBufferException;

import org.zeromq.ZContext;
import org.zeromq.ZFrame;
import org.zeromq.ZLoop;
import org.zeromq.ZMQ;
import org.zeromq.ZMsg;

import sawtooth.sdk.protobuf.Message;
import sawtooth.sdk.protobuf.MessageList;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Iterator;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;


/**
 * An internal messaging implementation used by the Stream class.
 */
class SendReceiveThread implements Runnable {

  private String url;
  private ZMQ.Socket socket;
  private Lock lock = new ReentrantLock();
  private Condition condition = lock.newCondition();
  private ConcurrentHashMap<String, FutureByteString> futures;
  private LinkedBlockingQueue<Message> receiveQueue;
  private ZContext context;

  public SendReceiveThread(String url,
                           ConcurrentHashMap<String, FutureByteString> futures,
                           LinkedBlockingQueue<Message> recvQueue) {
    super();
    this.url = url;
    this.futures = futures;
    this.receiveQueue = recvQueue;
    this.context = null;
  }

  /**
   * Inner class for receiving messages.
   */
  private class Receiver implements ZLoop.IZLoopHandler {

    private ConcurrentHashMap<String, FutureByteString> futures;
    private LinkedBlockingQueue<Message> receiveQueue;

    Receiver(ConcurrentHashMap<String, FutureByteString> futures,
             LinkedBlockingQueue<Message> receiveQueue) {
      this.futures = futures;
      this.receiveQueue = receiveQueue;
    }

    @Override
    public int handle(ZLoop loop, ZMQ.PollItem item, Object arg) {
      ZMsg msg = ZMsg.recvMsg(item.getSocket());
      Iterator<ZFrame> multiPartMessage = msg.iterator();

      ByteArrayOutputStream byteArrayOutputStream = new ByteArrayOutputStream();
      while (multiPartMessage.hasNext()) {
        ZFrame frame = multiPartMessage.next();
        try {
          byteArrayOutputStream.write(frame.getData());
        } catch (IOException ioe) {
          ioe.printStackTrace();
        }
      }
      try {
        MessageList messageList = MessageList.parseFrom(byteArrayOutputStream.toByteArray());
        for (Message message: messageList.getMessagesList()) {
          if (this.futures.containsKey(message.getCorrelationId())) {
            FutureByteString future = this.futures.get(message.getCorrelationId());
            future.setResult(message.getContent());
            this.futures.put(message.getCorrelationId(), future);
          } else {
            this.receiveQueue.put(message);
          }
        }
      } catch (InterruptedException ie) {
        ie.printStackTrace();
      } catch (InvalidProtocolBufferException ipe) {
        ipe.printStackTrace();
      }

      return 0;
    }
  }

  @Override
  public void run() {
    this.context = new ZContext();
    socket = this.context.createSocket(ZMQ.DEALER);
    socket.setIdentity((this.getClass().getName() + UUID.randomUUID().toString()).getBytes());
    socket.connect("tcp://" + url);
    lock.lock();
    try {
      condition.signalAll();
    } finally {
      lock.unlock();
    }
    ZLoop eventLoop = new ZLoop();
    ZMQ.PollItem pollItem = new ZMQ.PollItem(socket, ZMQ.Poller.POLLIN);
    eventLoop.addPoller(pollItem, new Receiver(futures, receiveQueue), new Object());
    eventLoop.start();
  }

  /**
   * Used by the Stream class to send a message.
   * @param message protobuf Message
   */
  public void sendMessage(Message message) {
    lock.lock();
    try {
      if (socket == null) {
        condition.await();
      }
    } catch (InterruptedException ie) {
      ie.printStackTrace();
    } finally {
      lock.unlock();
    }
    ZMsg msg = new ZMsg();
    msg.add(message.toByteString().toByteArray());
    msg.send(socket);
  }

  /**
   * Ends the zmq communication.
   */
  public void stop() {
    this.socket.close();
    this.context.destroy();
  }



}
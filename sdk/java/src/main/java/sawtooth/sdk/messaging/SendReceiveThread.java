/* Copyright 2016, 2017 Intel Corporation
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

package sawtooth.sdk.messaging;

import com.google.protobuf.InvalidProtocolBufferException;

import org.zeromq.ZContext;
import org.zeromq.ZFrame;
import org.zeromq.ZLoop;
import org.zeromq.ZMQ;
import org.zeromq.ZMsg;

import sawtooth.sdk.processor.exceptions.ValidatorConnectionError;

import sawtooth.sdk.protobuf.Message;

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
  private ConcurrentHashMap<String, Future> futures;
  private LinkedBlockingQueue<MessageWrapper> receiveQueue;
  private ZContext context;

  public SendReceiveThread(String url,
                           ConcurrentHashMap<String, Future> futures,
                           LinkedBlockingQueue<MessageWrapper> recvQueue) {
    super();
    this.url = url;
    this.futures = futures;
    this.receiveQueue = recvQueue;
    this.context = null;
  }

  /**
   * Inner class for passing messages.
   */
  public class MessageWrapper {
    Message message;

    public MessageWrapper(Message message) {
      this.message = message;
    }
  }

  private class DisconnectThread extends Thread {
    protected LinkedBlockingQueue<MessageWrapper> receiveQueue;
    protected ConcurrentHashMap<String, Future> futures;

    public DisconnectThread(LinkedBlockingQueue<MessageWrapper> receiveQueue,
        ConcurrentHashMap<String, Future> futures) {
      this.receiveQueue = receiveQueue;
      this.futures = futures;
    }
  }

  /**
   * Inner class for receiving messages.
   */
  private class Receiver implements ZLoop.IZLoopHandler {

    private ConcurrentHashMap<String, Future> futures;
    private LinkedBlockingQueue<MessageWrapper> receiveQueue;

    Receiver(ConcurrentHashMap<String, Future> futures,
             LinkedBlockingQueue<MessageWrapper> receiveQueue) {
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
        Message message = Message.parseFrom(byteArrayOutputStream.toByteArray());
        if (this.futures.containsKey(message.getCorrelationId())) {
          Future future = this.futures.get(message.getCorrelationId());
          future.setResult(message.getContent());
          this.futures.put(message.getCorrelationId(), future);
        } else {
          MessageWrapper wrapper = new MessageWrapper(message);
          this.receiveQueue.put(wrapper);
        }
      } catch (InterruptedException ie) {
        ie.printStackTrace();
      } catch (InvalidProtocolBufferException ipe) {
        ipe.printStackTrace();
      } catch (ValidatorConnectionError vce) {
        vce.printStackTrace();
      }


      return 0;
    }
  }

  @Override
  public void run() {
    this.context = new ZContext();
    socket = this.context.createSocket(ZMQ.DEALER);
    socket.monitor("inproc://monitor.s", ZMQ.EVENT_DISCONNECTED);
    final ZMQ.Socket monitor = this.context.createSocket(ZMQ.PAIR);
    monitor.connect("inproc://monitor.s");
    new DisconnectThread(this.receiveQueue, this.futures) {
      @Override
      public void run() {
        while (true) {
          // blocks until disconnect event recieved
          ZMQ.Event event = ZMQ.Event.recv(monitor);
          if (event.getEvent() == ZMQ.EVENT_DISCONNECTED) {
            try {
              MessageWrapper disconnectMsg = new MessageWrapper(null);
              for (String key: this.futures.keySet()) {
                Future future = new FutureError();
                this.futures.put(key, future);
              }
              this.receiveQueue.clear();
              this.receiveQueue.put(disconnectMsg);
            } catch (InterruptedException ie) {
              ie.printStackTrace();
            }
          }
        }
      }
    }.start();

    socket.setIdentity((this.getClass().getName() + UUID.randomUUID().toString()).getBytes());
    socket.connect(url);
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

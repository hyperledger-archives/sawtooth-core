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

import io.grpc.CallOptions;
import io.grpc.ClientCall;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.Metadata;

import sawtooth.sdk.protobuf.Message;
import sawtooth.sdk.protobuf.MessageList;
import sawtooth.sdk.protobuf.ValidatorGrpc;

import java.io.UnsupportedEncodingException;
import java.lang.String;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

/**
 * The client networking class.
 */
public class Stream {
  private ManagedChannel channel;

  private ClientCall<MessageList, MessageList> call;
  private ConcurrentHashMap<String, SettableFuture<ByteString>> futureHashMap;
  //This listener is for listening for MessageLists received
  private MessageListener messageListener;
  //This ExecutorService is for sending MessageLists
  private ExecutorService executorService;
  private LinkedBlockingQueue<Message> sendQueue;
  private LinkedBlockingQueue<Message> receiveQueue;
  private MessageListSender messageListSender;

  public static final String REGISTER = "tp/register";
  public static final String GET_REQUEST = "state/getrequest";
  public static final String SET_REQUEST = "state/setrequest";
  public static final String DELETE_REQUEST = "state/deleterequest";
  public static final String TP_RESPONSE = "tp/response";

  /**
   * The constructor.
   *
   * @param host a String representing the host, e.g. "localhost"
   * @param port the port, e.g. 40000
   */

  public Stream(String host, int port) {
    this.channel = ManagedChannelBuilder.forAddress(host, port).usePlaintext(true).build();
    this.sendQueue = new LinkedBlockingQueue<Message>();
  }

  /**
   * Make the initial connection with the Validator.
   */
  public void connect() {
    this.call = this.channel.newCall(ValidatorGrpc.METHOD_CONNECT, CallOptions.DEFAULT);
    this.futureHashMap = new ConcurrentHashMap<String, SettableFuture<ByteString>>();
    this.receiveQueue = new LinkedBlockingQueue<Message>();
    this.messageListener = new MessageListener(this.futureHashMap, this.receiveQueue);
    this.call.start(this.messageListener, new Metadata());
    this.call.request(Integer.MAX_VALUE);
    this.messageListSender = new MessageListSender(this.sendQueue, this.call);
    this.executorService = Executors.newFixedThreadPool(3);
    this.executorService.submit(this.messageListSender);
  }

  /**
   * Stop the Stream threads from running.
   */
  public void stop() {
    this.close();
    try {
      this.channel.awaitTermination(1, TimeUnit.SECONDS);
      this.executorService.shutdown();
      this.messageListSender.stopRunning();

    } catch (InterruptedException ie) {
      ie.printStackTrace();
    }
  }

  /**
   * Send a message and return a Future that will later have the Bytstring.
   * @param destination one of the static Strings in this class
   * @param contents the ByteString that has been serialized from a Protobuf class
   * @return future a future that will have ByteString that can be deserialized into a,
   *         for example, GetResponse
   */
  public SettableFuture<ByteString> send(String destination, ByteString contents) {
    Message message = Message.newBuilder()
            .setCorrelationId(this.generateId())
            .setMessageType(destination).setContent(contents).build();


    this.sendQueue.add(message);

    SettableFuture<ByteString> future = SettableFuture.create();
    this.futureHashMap.put(message.getCorrelationId(), future);

    return future;
  }

  /**
   * Send a message without getting a future back.
   * Useful for sending a response message to, for example, a transaction
   * @param destination one of the static Strings in this class
   * @param correlationId a random string generated on the server for the client to send back
   * @param contents ByteString serialized contents that the server is expecting
   */
  public void sendBack(String destination, String correlationId, ByteString contents) {
    Message message = Message.newBuilder()
            .setCorrelationId(correlationId)
            .setMessageType(destination).setContent(contents).build();


    this.sendQueue.add(message);
  }

  /**
   * Close the ClientCall, and tell the server that the client is disconnecting.
   */
  public void close() {
    Message message = Message.newBuilder()
            .setCorrelationId(this.generateId())
            .setMessageType("system/disconnect")
            .build();
    ArrayList<Message> messageArrayList = new ArrayList<Message>();
    messageArrayList.add(message);
    MessageList messageList = MessageList.newBuilder().addAllMessages(messageArrayList).build();
    this.call.sendMessage(messageList);
    this.call.halfClose();

  }

  /**
   * Get a message that has been received.
   * @return result, a protobuf Message
   */
  public Message receive() {

    Message result = null;
    try {
      result = this.receiveQueue.take();
    } catch (InterruptedException ie) {
      ie.printStackTrace();
    }
    return result;
  }

  /**
   * generate a random String using the sha-256 algorithm, to correlate sent messages.
   * with futures
   *
   * @return a random String
   */
  private String generateId() {
    StringBuilder stringBuilder = new StringBuilder();
    try {
      MessageDigest messageDigest = MessageDigest.getInstance("SHA-256");
      UUID uuid = UUID.randomUUID();
      byte[] dataRepresentingUuid = uuid.toString().getBytes("UTF-8");

      messageDigest.update(dataRepresentingUuid);


      byte[] digest = messageDigest.digest();

      for (int i = 0; i < digest.length; i++) {
        stringBuilder.append(Integer.toHexString(0xFF & digest[i]));
      }
    } catch (NoSuchAlgorithmException nsae) {
      nsae.printStackTrace();
    } catch (UnsupportedEncodingException usee) {
      usee.printStackTrace();
    }
    return stringBuilder.toString();
  }


}

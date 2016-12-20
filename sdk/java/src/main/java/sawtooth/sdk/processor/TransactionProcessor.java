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

package sawtooth.sdk.processor;


import com.google.protobuf.InvalidProtocolBufferException;

import sawtooth.sdk.client.State;
import sawtooth.sdk.client.Stream;
import sawtooth.sdk.processor.exceptions.InternalError;
import sawtooth.sdk.processor.exceptions.InvalidTransactionException;
import sawtooth.sdk.protobuf.Message;
import sawtooth.sdk.protobuf.TransactionProcessRequest;
import sawtooth.sdk.protobuf.TransactionProcessResponse;
import sawtooth.sdk.protobuf.TransactionProcessorRegisterRequest;


import java.util.ArrayList;
import java.util.logging.Level;
import java.util.logging.Logger;

public class TransactionProcessor implements Runnable {

  private final Logger logger = Logger.getLogger(TransactionProcessor.class.getName());

  private Stream stream;
  private ArrayList<TransactionHandler> handlers;
  private boolean isRunning;

  /**
   * constructor.
   * @param address the zmq address
   */
  public TransactionProcessor(String address) {
    this.stream = new Stream(address);
    this.handlers = new ArrayList<TransactionHandler>();
    this.isRunning = true;
  }

  /**
   * add a handler that will be run from within the run method.
   * @param handler implements that TransactionHandler interface
   */
  public void addHandler(TransactionHandler handler) {
    TransactionProcessorRegisterRequest registerRequest = TransactionProcessorRegisterRequest
            .newBuilder()
            .setFamily(handler.transactionFamilyName())
            .addAllNamespaces(handler.getNameSpaces())
            .setEncoding(handler.getEncoding())
            .setVersion(handler.getVersion())
            .build();
    this.stream.send(Stream.REGISTER, registerRequest.toByteString());
    this.handlers.add(handler);
  }


  public void stopRunning() {
    this.isRunning = false;
  }


  @Override
  public void run() {
    while (this.isRunning) {
      try {
        Message message = this.stream.receive();
        TransactionProcessRequest transactionRequest = TransactionProcessRequest
                .parseFrom(message.getContent());
        State state = new State(this.stream, transactionRequest.getContextId());
        if (!this.handlers.isEmpty()) {

          //FIXME get the right handler based on (encoding, version)...
          TransactionHandler handler = this.handlers.get(0);
          try {
            handler.apply(transactionRequest, state);
            TransactionProcessResponse response = TransactionProcessResponse.newBuilder()
                    .setStatus(TransactionProcessResponse.Status.OK).build();

            this.stream.sendBack(Stream.TP_RESPONSE,
                    message.getCorrelationId(),
                    response.toByteString());
          } catch (InvalidTransactionException ite) {
            ite.printStackTrace();
            logger.log(Level.WARNING, "Invalid Transaction");
            TransactionProcessResponse response = TransactionProcessResponse.newBuilder()
                    .setStatus(TransactionProcessResponse.Status.INVALID_TRANSACTION)
                    .build();
            this.stream.sendBack(Stream.TP_RESPONSE,
                    message.getCorrelationId(),
                    response.toByteString());
          } catch (InternalError ie) {
            ie.printStackTrace();
            logger.log(Level.WARNING, "State Exception!");
            TransactionProcessResponse response = TransactionProcessResponse.newBuilder()
                    .setStatus(TransactionProcessResponse.Status.INTERNAL_ERROR)
                    .build();
            this.stream.sendBack(Stream.TP_RESPONSE,
                    message.getCorrelationId(),
                    response.toByteString());
          }
        }


      } catch (InvalidProtocolBufferException ipbe) {
        logger.info(
                "Received Bytestring that wasn't requested that isn't TransactionProcessRequest");
        ipbe.printStackTrace();
      }
    }
  }

}

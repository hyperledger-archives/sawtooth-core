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

package sawtooth.sdk.processor;

import com.google.protobuf.ByteString;
import com.google.protobuf.InvalidProtocolBufferException;

import sawtooth.sdk.messaging.Future;
import sawtooth.sdk.messaging.Stream;
import sawtooth.sdk.processor.exceptions.InternalError;
import sawtooth.sdk.processor.exceptions.InvalidTransactionException;
import sawtooth.sdk.processor.exceptions.ValidatorConnectionError;
import sawtooth.sdk.protobuf.Message;
import sawtooth.sdk.protobuf.PingResponse;
import sawtooth.sdk.protobuf.TpProcessRequest;
import sawtooth.sdk.protobuf.TpProcessResponse;
import sawtooth.sdk.protobuf.TpRegisterRequest;
import sawtooth.sdk.protobuf.TpUnregisterRequest;
import sawtooth.sdk.protobuf.TransactionHeader;

import java.util.ArrayList;
import java.util.concurrent.TimeoutException;
import java.util.logging.Level;
import java.util.logging.Logger;


public class TransactionProcessor implements Runnable {

  private static final Logger logger = Logger.getLogger(TransactionProcessor.class.getName());

  private Stream stream;
  private ArrayList<TransactionHandler> handlers;
  private Message currentMessage;
  private boolean registered;

  class Shutdown extends Thread {
    @Override
    public void run() {
      logger.info("Start Shutdown of Transaction Processor.");
      if (!TransactionProcessor.this.registered) {
        return;
      }
      if (TransactionProcessor.this.getCurrentMessage() != null) {
        logger.info(TransactionProcessor.this.getCurrentMessage().toString());
      }
      try {
        TpUnregisterRequest unregisterRequest = TpUnregisterRequest
                .newBuilder()
                .build();
        logger.info("Send TpUnregisterRequest");
        Future fut = TransactionProcessor.this.stream.send(
            Message.MessageType.TP_UNREGISTER_REQUEST, unregisterRequest.toByteString());
        ByteString response = fut.getResult(1);
        Message message = TransactionProcessor.this.getCurrentMessage();
        if (message == null) {
          message = TransactionProcessor.this.stream.receive(1);
        }
        logger.info("Finish processing any left over messages.");
        while (message != null) {
          TransactionHandler handler = TransactionProcessor.this.findHandler(message);
          TransactionProcessor.process(message, TransactionProcessor.this.stream, handler);
          message = TransactionProcessor.this.stream.receive(1);
        }
      } catch (InterruptedException ie) {
        ie.printStackTrace();
      } catch (TimeoutException ter) {
        logger.info("TimeoutException on shutdown");
      } catch (ValidatorConnectionError vce) {
        logger.info(vce.toString());
      }
    }
  }

  /**
   * constructor.
   * @param address the zmq address
   */
  public TransactionProcessor(String address) {
    this.stream = new Stream(address);
    this.handlers = new ArrayList<TransactionHandler>();
    this.currentMessage = null;
    this.registered = false;
    Runtime.getRuntime().addShutdownHook(new Shutdown());
  }

  /**
   * add a handler that will be run from within the run method.
   * @param handler implements that TransactionHandler interface
   */
  public void addHandler(TransactionHandler handler) {
    TpRegisterRequest registerRequest = TpRegisterRequest
            .newBuilder()
            .setFamily(handler.transactionFamilyName())
            .addAllNamespaces(handler.getNameSpaces())
            .setVersion(handler.getVersion())
            .setMaxOccupancy(1)
            .build();
    try {
      Future fut = this.stream.send(
          Message.MessageType.TP_REGISTER_REQUEST, registerRequest.toByteString());
      fut.getResult();
      this.registered = true;
      this.handlers.add(handler);
    } catch (InterruptedException ie) {
      ie.printStackTrace();
    } catch (ValidatorConnectionError vce) {
      logger.info(vce.toString());
    }
  }

  /**
  * Get the current message that is being processed.
  */
  private Message getCurrentMessage() {
    return this.currentMessage;
  }

  /**
  * Used to process a message.
  * @param message The Message to process.
  * @param stream The Stream to use to send back responses.
  * @param handler The handler that should be used to process the message.
  */
  private static void process(Message message, Stream stream,
      TransactionHandler handler) {
    try {
      TpProcessRequest transactionRequest = TpProcessRequest
              .parseFrom(message.getContent());
      State state = new State(stream, transactionRequest.getContextId());

      TpProcessResponse.Builder builder = TpProcessResponse.newBuilder();
      try {
        handler.apply(transactionRequest, state);
        builder.setStatus(TpProcessResponse.Status.OK);
      } catch (InvalidTransactionException ite) {
        logger.log(Level.WARNING, "Invalid Transaction: " + ite.toString());
        builder.setStatus(TpProcessResponse.Status.INVALID_TRANSACTION);
        builder.setMessage(ite.getMessage());
        if (ite.getExtendedData() != null) {
          builder.setExtendedData(ByteString.copyFrom(ite.getExtendedData()));
        }
      } catch (InternalError ie) {
        logger.log(Level.WARNING, "State Exception!: " + ie.toString());
        builder.setStatus(TpProcessResponse.Status.INTERNAL_ERROR);
        builder.setMessage(ie.getMessage());
        if (ie.getExtendedData() != null) {
          builder.setExtendedData(ByteString.copyFrom(ie.getExtendedData()));
        }
      }
      stream.sendBack(Message.MessageType.TP_PROCESS_RESPONSE,
              message.getCorrelationId(),
              builder.build().toByteString());

    } catch (InvalidProtocolBufferException ipbe) {
      logger.info(
              "Received Bytestring that wasn't requested that isn't TransactionProcessRequest");
    }
  }

  /**
  * Find the handler that should be used to process the given message.
  * @param message The message that has the TpProcessRequest that the header
  *                that will be checked against the handler.
  */
  private TransactionHandler findHandler(Message message) {
    try {
      TpProcessRequest transactionRequest = TpProcessRequest
              .parseFrom(this.currentMessage.getContent());
      TransactionHeader header = transactionRequest.getHeader();
      for (int  i = 0; i < this.handlers.size(); i++) {
        TransactionHandler handler = this.handlers.get(i);
        if (header.getFamilyName().equals(handler.transactionFamilyName())
            && header.getFamilyVersion().equals(handler.getVersion())) {
          return handler;
        }
      }
      logger.info("Missing handler for header: " + header.toString());
    } catch (InvalidProtocolBufferException ipbe) {
      logger.info(
              "Received Message that isn't a TransactionProcessRequest");
      ipbe.printStackTrace();
    }
    return null;
  }

  @Override
  public void run() {
    while (true) {
      if (!this.handlers.isEmpty()) {
        this.currentMessage = this.stream.receive();
        if (this.currentMessage != null) {
          if (this.currentMessage.getMessageType() == Message.MessageType.PING_REQUEST) {
            logger.info("Recieved Ping Message.");
            PingResponse pingResponse = PingResponse
                .newBuilder()
                .build();
            this.stream.sendBack(
                Message.MessageType.PING_RESPONSE,
                this.currentMessage.getCorrelationId(),
                pingResponse.toByteString());
            this.currentMessage = null;
          } else if (this.currentMessage.getMessageType()
                == Message.MessageType.TP_PROCESS_REQUEST) {
            TransactionHandler handler = this.findHandler(this.currentMessage);
            if (handler == null) {
              break;
            }
            TransactionProcessor.process(this.currentMessage, this.stream, handler);
            this.currentMessage = null;
          } else {
            logger.info("Unknown Message Type: " + this.currentMessage.getMessageType());
            this.currentMessage = null;
          }
        } else {
          // Disconnect
          logger.info("The Validator disconnected, trying to register.");
          this.registered = false;
          for (int i = 0; i < this.handlers.size(); i++) {
            TransactionHandler handler = this.handlers.get(i);
            TpRegisterRequest registerRequest = TpRegisterRequest
                    .newBuilder()
                    .setFamily(handler.transactionFamilyName())
                    .addAllNamespaces(handler.getNameSpaces())
                    .setVersion(handler.getVersion())
                    .build();

            try {
              Future fut = this.stream.send(
                  Message.MessageType.TP_REGISTER_REQUEST, registerRequest.toByteString());
              fut.getResult();
              this.registered = true;
            } catch (InterruptedException ie) {
              logger.log(Level.WARNING, ie.toString());
            }  catch (ValidatorConnectionError vce) {
              logger.log(Level.WARNING, vce.toString());
            }
          }
        }
      }
    }
  }
}

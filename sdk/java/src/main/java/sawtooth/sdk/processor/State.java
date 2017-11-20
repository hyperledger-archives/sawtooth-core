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
import sawtooth.sdk.protobuf.TpStateEntry;
import sawtooth.sdk.protobuf.TpStateGetRequest;
import sawtooth.sdk.protobuf.TpStateGetResponse;
import sawtooth.sdk.protobuf.TpStateSetRequest;
import sawtooth.sdk.protobuf.TpStateSetResponse;


import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.Map;


/**
 * Client state that interacts with the context manager through Stream networking.
 */
public class State {

  private Stream stream;
  private String contextId;
  private static final int TIME_OUT = 2;

  public State(Stream stream, String contextId) {
    this.stream = stream;
    this.contextId = contextId;
  }

  /**
   * Make a Get request on a specific context specified by contextId.
   *
   * @param addresses a collection of address Strings
   * @return Map where the keys are addresses, values Bytestring
   * @throws InternalError something went wrong processing transaction
   */
  public Map<String, ByteString> getState(Collection<String> addresses)
      throws InternalError, InvalidTransactionException {
    TpStateGetRequest getRequest = TpStateGetRequest.newBuilder()
            .addAllAddresses(addresses)
            .setContextId(this.contextId).build();
    Future future = stream.send(Message.MessageType.TP_STATE_GET_REQUEST,
        getRequest.toByteString());
    TpStateGetResponse getResponse = null;
    try {
      getResponse = TpStateGetResponse.parseFrom(future.getResult(TIME_OUT));
    } catch (InterruptedException iee) {
      throw new InternalError(iee.toString());
    } catch (InvalidProtocolBufferException ipbe) {
      // server didn't respond with a GetResponse
      throw new InternalError(ipbe.toString());
    } catch (ValidatorConnectionError vce) {
      throw new InternalError(vce.toString());
    } catch (Exception e) {
      throw new InternalError(e.toString());
    }
    Map<String, ByteString> results = new HashMap<String, ByteString>();
    if (getResponse != null) {
      if (getResponse.getStatus() == TpStateGetResponse.Status.AUTHORIZATION_ERROR) {
        throw new InvalidTransactionException(
          "Tried to get unauthorized address " + addresses.toString()) ;
      }
      for (TpStateEntry entry : getResponse.getEntriesList()) {
        results.put(entry.getAddress(), entry.getData());
      }
    }
    if (results.isEmpty()) {
      throw new InternalError(
        "State Error, no result found for get request:" + addresses.toString());
    }

    return results;
  }

  /**
   * Make a Set request on a specific context specified by contextId.
   *
   * @param addressValuePairs A collection of Map.Entry's
   * @return addressesThatWereSet, A collection of address Strings that were set
   * @throws InternalError something went wrong processing transaction
   */
  public Collection<String> setState(Collection<java.util.Map.Entry<String,
          ByteString>> addressValuePairs) throws InternalError, InvalidTransactionException {
    ArrayList<TpStateEntry> entryArrayList = new ArrayList<TpStateEntry>();
    for (Map.Entry<String, ByteString> entry : addressValuePairs) {
      TpStateEntry ourTpStateEntry = TpStateEntry.newBuilder()
              .setAddress(entry.getKey())
              .setData(entry.getValue())
              .build();
      entryArrayList.add(ourTpStateEntry);
    }
    TpStateSetRequest setRequest = TpStateSetRequest.newBuilder()
            .addAllEntries(entryArrayList)
            .setContextId(this.contextId).build();
    Future future = stream.send(Message.MessageType.TP_STATE_SET_REQUEST,
        setRequest.toByteString());
    TpStateSetResponse setResponse = null;
    try {
      setResponse = TpStateSetResponse.parseFrom(future.getResult(TIME_OUT));
    } catch (InterruptedException iee) {
      throw new InternalError(iee.toString());

    } catch (InvalidProtocolBufferException ipbe) {
      // server didn't respond with a SetResponse
      throw new InternalError(ipbe.toString());
    } catch (ValidatorConnectionError vce) {
      throw new InternalError(vce.toString());
    } catch (Exception e) {
      throw new InternalError(e.toString());
    }
    ArrayList<String> addressesThatWereSet = new ArrayList<String>();
    if (setResponse != null) {
      if (setResponse.getStatus() == TpStateSetResponse.Status.AUTHORIZATION_ERROR) {
        throw new InvalidTransactionException(
          "Tried to set unauthorized address " + addressValuePairs.toString());
      }
      for (String address : setResponse.getAddressesList()) {
        addressesThatWereSet.add(address);
      }
    }

    return addressesThatWereSet;
  }

}

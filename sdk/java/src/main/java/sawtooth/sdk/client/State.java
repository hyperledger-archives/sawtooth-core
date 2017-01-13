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

import com.google.protobuf.ByteString;
import com.google.protobuf.InvalidProtocolBufferException;

import sawtooth.sdk.processor.exceptions.InternalError;
import sawtooth.sdk.protobuf.Entry;
import sawtooth.sdk.protobuf.Message;
import sawtooth.sdk.protobuf.TpStateGetRequest;
import sawtooth.sdk.protobuf.TpStateGetResponse;
import sawtooth.sdk.protobuf.TpStateSetRequest;
import sawtooth.sdk.protobuf.TpStateSetResponse;


import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.TimeoutException;


/**
 * Client state that interacts with the context manager through Stream networking.
 */
public class State {

  private Stream stream;
  private String contextId;

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
  public Map<String, ByteString> get(Collection<String> addresses) throws InternalError {

    TpStateGetRequest getRequest = TpStateGetRequest.newBuilder()
            .addAllAddresses(addresses)
            .setContextId(this.contextId).build();
    FutureByteString future = stream.send(Message.MessageType.TP_STATE_GET_REQUEST,
        getRequest.toByteString());
    TpStateGetResponse getResponse = null;
    try {
      getResponse = TpStateGetResponse.parseFrom(future.getResult());
    } catch (TimeoutException toe) {
      try {
        getResponse = TpStateGetResponse.parseFrom(future.getResult());
      } catch (Exception e) {
        throw new InternalError(e.toString());
      }
    } catch (InterruptedException iee) {
      throw new InternalError(iee.toString());
    } catch (InvalidProtocolBufferException ipbe) {
      // server didn't respond with a GetResponse
      throw new InternalError(ipbe.toString());
    }
    Map<String, ByteString> results = new HashMap<String, ByteString>();
    if (getResponse != null) {
      for (Entry entry : getResponse.getEntriesList()) {
        results.put(entry.getAddress(), entry.getData());
      }
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
  public Collection<String> set(Collection<java.util.Map.Entry<String,
          ByteString>> addressValuePairs) throws InternalError {
    ArrayList<Entry> entryArrayList = new ArrayList<Entry>();
    for (Map.Entry<String, ByteString> entry : addressValuePairs) {
      Entry ourEntry = Entry.newBuilder()
              .setAddress(entry.getKey())
              .setData(entry.getValue())
              .build();
      entryArrayList.add(ourEntry);
    }
    TpStateSetRequest setRequest = TpStateSetRequest.newBuilder()
            .addAllEntries(entryArrayList)
            .setContextId(this.contextId).build();
    FutureByteString future = stream.send(Message.MessageType.TP_STATE_SET_REQUEST,
        setRequest.toByteString());
    TpStateSetResponse setResponse = null;
    try {
      setResponse = TpStateSetResponse.parseFrom(future.getResult());
    } catch (TimeoutException toe) {
      try {
        setResponse = TpStateSetResponse.parseFrom(future.getResult());
      } catch (Exception e) {
        throw new InternalError(e.toString());
      }
    } catch (InterruptedException iee) {
      throw new InternalError(iee.toString());

    } catch (InvalidProtocolBufferException ipbe) {
      // server didn't respond with a SetResponse
      throw new InternalError(ipbe.toString());
    }
    ArrayList<String> addressesThatWereSet = new ArrayList<String>();
    if (setResponse != null) {
      for (String address : setResponse.getAddressesList()) {
        addressesThatWereSet.add(address);
      }
    }
    return addressesThatWereSet;
  }

}

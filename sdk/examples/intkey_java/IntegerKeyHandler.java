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

package sawtooth.examples.intkey;

import com.google.protobuf.ByteString;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.cbor.CBORFactory;

import sawtooth.sdk.client.State;
import sawtooth.sdk.client.Utils;
import sawtooth.sdk.processor.TransactionHandler;
import sawtooth.sdk.processor.exceptions.InternalError;
import sawtooth.sdk.processor.exceptions.InvalidTransactionException;
import sawtooth.sdk.protobuf.TransactionProcessRequest;

import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.util.AbstractMap;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashMap;
import java.util.Map;
import java.util.logging.Logger;


public class IntegerKeyHandler implements TransactionHandler {

  private ObjectMapper mapper;
  private final Logger logger = Logger.getLogger(IntegerKeyHandler.class.getName());
  private String intkeyNameSpace;

  /**
   * constructor.
   */
  public IntegerKeyHandler() {
    CBORFactory factory = new CBORFactory();
    this.mapper = new ObjectMapper(factory);
    try {
      this.intkeyNameSpace = Utils.hash512(
              this.transactionFamilyName().getBytes("UTF-8")).substring(0, 6);
    } catch (UnsupportedEncodingException usee) {
      usee.printStackTrace();
      this.intkeyNameSpace = "";
    }
  }

  @Override
  public String transactionFamilyName() {
    return "intkey";
  }

  @Override
  public String getEncoding() {
    return "application/cbor";
  }

  @Override
  public String getVersion() {
    return "1.0";
  }

  @Override
  public Collection<String> getNameSpaces() {
    ArrayList<String> namespaces = new ArrayList<String>();
    namespaces.add(this.intkeyNameSpace);
    return namespaces;
  }

  @Override
  public void apply(TransactionProcessRequest transactionRequest,
                    State state) throws InvalidTransactionException, InternalError {
    try {
      HashMap updateMap = this.mapper.readValue(
              transactionRequest.getPayload().toByteArray(), HashMap.class);
      String name = Utils.stringByteArrayToString((byte[]) updateMap.get("Name"));
      String address = null;
      try {
        address = this.intkeyNameSpace + Utils.hash512(name.getBytes("UTF-8"));
      } catch (UnsupportedEncodingException usee) {
        usee.printStackTrace();
        throw new InternalError("Internal Error, " + usee.toString());
      }
      if (name.length() == 0) {
        throw new InvalidTransactionException("Name is required");
      }
      String verb = Utils.stringByteArrayToString((byte[]) updateMap.get("Verb"));
      if (verb.length() == 0) {
        throw new InvalidTransactionException("Verb is required");
      }
      Integer value = Integer.decode(updateMap.get("Value").toString());
      if (value == null) {
        throw new InvalidTransactionException("Value is required");
      }

      if (!Arrays.asList("set", "dec", "inc").contains(verb)) {
        throw new InvalidTransactionException("Verb must be set, inc, dec not " + verb);
      }
      Collection<String> addresses = new ArrayList<String>(0);
      if (verb.equals("set")) {
        // if it is a 'set', get the address and see if there is a value there
        Map<String, ByteString> possibleAddressValues = state.get(Arrays.asList(address));
        // The String representation of the state 'value'
        String stateValue = Utils.stringByteArrayToString(
                possibleAddressValues.get(address).toByteArray());

        if (!(stateValue.length() == 0)) {
          throw new InvalidTransactionException(
                  "Verb is 'set' but Name already in state, Name: "
                          + name + " Value: "
                          + Utils.stringByteArrayToString(
                                  possibleAddressValues.get(address).toByteArray()));
        }
        if (value < 0) {
          throw new InvalidTransactionException("Verb is set but Value is less than 0");
        }
        // 'set' passes checks so store it in the state
        Map.Entry<String, ByteString> entry = new AbstractMap.SimpleEntry<String, ByteString>(
                address,
                ByteString.copyFrom(value.toString().getBytes("UTF-8")));

        Collection<Map.Entry<String, ByteString>> addressValues = Arrays.asList(entry);
        addresses = state.set(addressValues);
      }
      if (verb.equals("inc")) {
        Map<String, ByteString> possibleValue = state.get(Arrays.asList(address));
        String stateValue = Utils.stringByteArrayToString(possibleValue.get(address).toByteArray());
        if (stateValue.length() == 0) {
          throw new InvalidTransactionException("Verb is inc but Name is not in state");
        }

        // Increment the value in state by value
        Integer newValue = Integer.decode(stateValue) + value;
        Map.Entry<String, ByteString> entry = new AbstractMap.SimpleEntry<String, ByteString>(
                address,
                ByteString.copyFrom(Integer.toString(newValue).getBytes("UTF-8")));
        Collection<Map.Entry<String, ByteString>> addressValues = Arrays.asList(entry);
        addresses = state.set(addressValues);
      }
      if (verb.equals("dec")) {
        Map<String, ByteString> possibleAddressResult = state.get(Arrays.asList(address));
        String stateValue = Utils.stringByteArrayToString(
                possibleAddressResult.get(address).toByteArray());

        if (stateValue.length() == 0) {
          throw new InvalidTransactionException("Verb is dec but Name is not in state");
        }
        if (Integer.decode(stateValue) - value < 0) {
          throw new InvalidTransactionException("Dec would set Value to less than 0");
        }
        // Decrement the value in state by value
        Integer newValue = Integer.decode(stateValue) - value;
        Map.Entry<String, ByteString> entry = new AbstractMap.SimpleEntry<String, ByteString>(
                address,
                ByteString.copyFrom(Integer.toString(newValue).getBytes("UTF-8")));

        Collection<Map.Entry<String, ByteString>> addressValues = Arrays.asList(entry);
        addresses = state.set(addressValues);
      }
      // if the 'set', 'inc', or 'dec' set to state didn't work
      if (addresses.size() == 0) {
        throw new InternalError("State error!.");
      }
      logger.info("Verb: " + verb + " Name: " + name + " value: " + value);

    } catch (IOException ioe) {
      ioe.printStackTrace();
      throw new InternalError("State error");
    }

  }

}

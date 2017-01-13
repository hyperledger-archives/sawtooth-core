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
import sawtooth.sdk.protobuf.TpProcessRequest;

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
  public void apply(TpProcessRequest transactionRequest,
                    State state) throws InvalidTransactionException, InternalError {
    /*
     * Integer Key state will be stored at an address of the name
     * with the key being the name and the value an Integer. so { "foo": 20, "bar": 26}
     * would be a possibility if the hashing algorithm hashes foo and bar to the
     * same address
     */
    try {
      HashMap updateMap = this.mapper.readValue(
              transactionRequest.getPayload().toByteArray(), HashMap.class);
      String name = updateMap.get("Name").toString();
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
      String verb = updateMap.get("Verb").toString();
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
        // The ByteString is cbor encoded dict/hashmap
        Map<String, ByteString> possibleAddressValues = state.get(Arrays.asList(address));
        byte[] stateValueRep = possibleAddressValues.get(address).toByteArray();
        Map<String, Integer> stateValue = null;
        if (stateValueRep.length > 0) {
          stateValue = this.mapper.readValue(stateValueRep, HashMap.class);
          if (stateValue.containsKey(name)) {
            throw new InvalidTransactionException("Verb is set but Name already in state, "
                    + "Name: " + name + " Value: " + stateValue.get(name).toString());
          }
        }

        if (value < 0) {
          throw new InvalidTransactionException("Verb is set but Value is less than 0");
        }
        // 'set' passes checks so store it in the state
        if (stateValue == null) {
          stateValue = new HashMap<String, Integer>();
        }
        Map<String,Integer> setValue = stateValue;
        setValue.put(name, value);
        Map.Entry<String, ByteString> entry = new AbstractMap.SimpleEntry<String, ByteString>(
                address,
                ByteString.copyFrom(this.mapper.writeValueAsBytes(setValue)));

        Collection<Map.Entry<String, ByteString>> addressValues = Arrays.asList(entry);
        addresses = state.set(addressValues);
      }
      if (verb.equals("inc")) {
        Map<String, ByteString> possibleValues = state.get(Arrays.asList(address));
        byte[] stateValueRep = possibleValues.get(address).toByteArray();
        if (stateValueRep.length == 0) {
          throw new InvalidTransactionException("Verb is inc but Name is not in state");
        }
        Map<String, Integer> stateValue = this.mapper.readValue(
                stateValueRep, HashMap.class);
        if (!stateValue.containsKey(name)) {
          throw new InvalidTransactionException("Verb is inc but Name is not in state");
        }

        // Increment the value in state by value
        Map<String, Integer> incValue = stateValue;
        incValue.put(name, stateValue.get(name) + value);
        Map.Entry<String, ByteString> entry = new AbstractMap.SimpleEntry<String, ByteString>(
                address,
                ByteString.copyFrom(this.mapper.writeValueAsBytes(incValue)));
        Collection<Map.Entry<String, ByteString>> addressValues = Arrays.asList(entry);
        addresses = state.set(addressValues);
      }
      if (verb.equals("dec")) {
        Map<String, ByteString> possibleAddressResult = state.get(Arrays.asList(address));
        byte[] stateValueRep = possibleAddressResult.get(address).toByteArray();

        if (stateValueRep.length == 0) {
          throw new InvalidTransactionException("Verb is dec but Name is not in state");
        }
        Map<String, Integer> stateValue = this.mapper.readValue(stateValueRep, HashMap.class);
        if (!stateValue.containsKey(name)) {
          throw new InvalidTransactionException("Verb is dec but Name is not in state");
        }
        if (stateValue.get(name) - value < 0) {
          throw new InvalidTransactionException("Dec would set Value to less than 0");
        }
        Map<String, Integer> decValue = stateValue;
        // Decrement the value in state by value
        decValue.put(name, stateValue.get(name) - value);
        Map.Entry<String, ByteString> entry = new AbstractMap.SimpleEntry<String, ByteString>(
                address,
                ByteString.copyFrom(this.mapper.writeValueAsBytes(decValue)));

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
      throw new InternalError("State error" + ioe.toString());
    }
  }
}

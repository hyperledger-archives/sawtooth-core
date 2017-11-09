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

package sawtooth.examples.intkey;

import com.google.protobuf.ByteString;

import co.nstant.in.cbor.CborBuilder;
import co.nstant.in.cbor.CborDecoder;
import co.nstant.in.cbor.CborEncoder;
import co.nstant.in.cbor.CborException;
import co.nstant.in.cbor.model.DataItem;

import sawtooth.sdk.processor.State;
import sawtooth.sdk.processor.TransactionHandler;
import sawtooth.sdk.processor.Utils;
import sawtooth.sdk.processor.exceptions.InternalError;
import sawtooth.sdk.processor.exceptions.InvalidTransactionException;
import sawtooth.sdk.protobuf.TpProcessRequest;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
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

  private final Logger logger = Logger.getLogger(IntegerKeyHandler.class.getName());
  private String intkeyNameSpace;

  private static final long MIN_VALUE = 0;
  private static final long MAX_VALUE = 4294967295L;
  private static final long MAX_NAME_LENGTH = 20;

  /**
   * constructor.
   */
  public IntegerKeyHandler() {
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
  public String getVersion() {
    return "1.0";
  }

  @Override
  public Collection<String> getNameSpaces() {
    ArrayList<String> namespaces = new ArrayList<String>();
    namespaces.add(this.intkeyNameSpace);
    return namespaces;
  }

  /**
   * Helper function to decode the Payload of a transaction.
   * Convert the co.nstant.in.cbor.model.Map to a HashMap.
   */
  public Map<String, String> decodePayload(byte[] bytes) throws CborException {
    ByteArrayInputStream bais = new ByteArrayInputStream(bytes);
    co.nstant.in.cbor.model.Map data =
        (co.nstant.in.cbor.model.Map) new CborDecoder(bais).decodeNext();
    DataItem[] keys = data.getKeys().toArray(new DataItem[0]);
    Map<String, String> result = new HashMap();
    for (int i = 0; i < keys.length; i++) {
      result.put(
          keys[i].toString(),
          data.get(keys[i]).toString());
    }
    return result;
  }

  /**
   * Helper function to decode State retrieved from the address of the name.
   * Convert the co.nstant.in.cbor.model.Map to a HashMap.
   */
  public Map<String, Long> decodeState(byte[] bytes) throws CborException {
    ByteArrayInputStream bais = new ByteArrayInputStream(bytes);
    co.nstant.in.cbor.model.Map data =
        (co.nstant.in.cbor.model.Map) new CborDecoder(bais).decodeNext();
    DataItem[] keys = data.getKeys().toArray(new DataItem[0]);
    Map<String, Long> result = new HashMap();
    for (int i = 0; i < keys.length; i++) {
      result.put(
          keys[i].toString(),
          Long.decode(data.get(keys[i]).toString()));
    }
    return result;
  }

  /**
   * Helper function to encode the State that will be stored at the address of
   * the name.
   */
  public Map.Entry<String, ByteString> encodeState(String address, String name, Long value)
      throws CborException {
    ByteArrayOutputStream boas = new ByteArrayOutputStream();
    new CborEncoder(boas).encode(new CborBuilder()
        .addMap()
        .put(name, value)
        .end()
        .build());

    return new AbstractMap.SimpleEntry<String, ByteString>(
        address,
        ByteString.copyFrom(boas.toByteArray()));
  }

  @Override
  public void apply(TpProcessRequest transactionRequest,
                    State state) throws InvalidTransactionException, InternalError {
    /*
     * IntKey state will be stored at an address of the name
     * with the key being the name and the value an integer. so { "foo": 20, "bar": 26}
     * would be a possibility if the hashing algorithm hashes foo and bar to the
     * same address
     */
    try {
      if (transactionRequest.getPayload().size() == 0) {
        throw new InvalidTransactionException("Payload is required.");
      }

      Map updateMap = this.decodePayload(transactionRequest.getPayload().toByteArray());

      // validate name
      String name = updateMap.get("Name").toString();

      if (name.length() == 0) {
        throw new InvalidTransactionException("Name is required");
      }

      if (name.length() > MAX_NAME_LENGTH) {
        throw new InvalidTransactionException(
          "Name must be a string of no more than "
          + Long.toString(MAX_NAME_LENGTH) + " characters");
      }

      // validate verb
      String verb = updateMap.get("Verb").toString();

      if (verb.length() == 0) {
        throw new InvalidTransactionException("Verb is required");
      }

      if (!Arrays.asList("set", "dec", "inc").contains(verb)) {
        throw new InvalidTransactionException(
          "Verb must be set, inc, or dec, not " + verb);
      }

      // validate value
      Long value = null;

      try {
        value = Long.decode(updateMap.get("Value").toString());
      } catch (NumberFormatException ex) {
        throw new InvalidTransactionException(
          "Value must be an integer");
      }

      if (value == null) {
        throw new InvalidTransactionException("Value is required");
      }

      if (value > MAX_VALUE || value < MIN_VALUE) {
        throw new InvalidTransactionException(
          "Value must be an integer "
          + "no less than " + Long.toString(MIN_VALUE)
          + " and no greater than " + Long.toString(MAX_VALUE));
      }

      String address = null;

      try {
        String hashedName = Utils.hash512(name.getBytes("UTF-8"));
        address = this.intkeyNameSpace + hashedName.substring(hashedName.length() - 64);
      } catch (UnsupportedEncodingException usee) {
        usee.printStackTrace();
        throw new InternalError("Internal Error, " + usee.toString());
      }

      Collection<String> addresses = new ArrayList<String>(0);

      if (verb.equals("set")) {
        // The ByteString is cbor encoded dict/hashmap
        Map<String, ByteString> possibleAddressValues = state.getState(Arrays.asList(address));
        byte[] stateValueRep = possibleAddressValues.get(address).toByteArray();
        Map<String, Long> stateValue = null;
        if (stateValueRep.length > 0) {
          stateValue = this.decodeState(stateValueRep);
          if (stateValue.containsKey(name)) {
            throw new InvalidTransactionException("Verb is set but Name already in state, "
                    + "Name: " + name + " Value: " + stateValue.get(name).toString());
          }
        }

        if (value < 0) {
          throw new InvalidTransactionException("Verb is set but Value is less than 0");
        }

        // 'set' passes checks so store it in the state
        Map.Entry<String, ByteString> entry = this.encodeState(address, name, value);

        Collection<Map.Entry<String, ByteString>> addressValues = Arrays.asList(entry);
        addresses = state.setState(addressValues);
      }
      if (verb.equals("inc")) {
        Map<String, ByteString> possibleValues = state.getState(Arrays.asList(address));
        byte[] stateValueRep = possibleValues.get(address).toByteArray();
        if (stateValueRep.length == 0) {
          throw new InvalidTransactionException("Verb is inc but Name is not in state");
        }
        Map<String, Long> stateValue = this.decodeState(stateValueRep);
        if (!stateValue.containsKey(name)) {
          throw new InvalidTransactionException("Verb is inc but Name is not in state");
        }
        if (stateValue.get(name) + value > MAX_VALUE) {
          throw new InvalidTransactionException(
            "Inc would set Value to greater than " + Long.toString(MAX_VALUE));
        }
        // Increment the value in state by value
        Map.Entry<String, ByteString> entry =
            this.encodeState(address, name, stateValue.get(name) + value);
        Collection<Map.Entry<String, ByteString>> addressValues = Arrays.asList(entry);
        addresses = state.setState(addressValues);
      }
      if (verb.equals("dec")) {
        Map<String, ByteString> possibleAddressResult = state.getState(Arrays.asList(address));
        byte[] stateValueRep = possibleAddressResult.get(address).toByteArray();

        if (stateValueRep.length == 0) {
          throw new InvalidTransactionException("Verb is dec but Name is not in state");
        }
        Map<String, Long> stateValue = this.decodeState(stateValueRep);
        if (!stateValue.containsKey(name)) {
          throw new InvalidTransactionException("Verb is dec but Name is not in state");
        }
        if (stateValue.get(name) - value < MIN_VALUE) {
          throw new InvalidTransactionException(
            "Dec would set Value to less than " + Long.toString(MIN_VALUE));
        }

        // Decrement the value in state by value
        Map.Entry<String, ByteString> entry =
            this.encodeState(address, name, stateValue.get(name) - value);

        Collection<Map.Entry<String, ByteString>> addressValues = Arrays.asList(entry);
        addresses = state.setState(addressValues);
      }
      // if the 'set', 'inc', or 'dec' set to state didn't work
      if (addresses.size() == 0) {
        throw new InternalError("State error!.");
      }
      logger.info("Verb: " + verb + " Name: " + name + " value: " + value);

    } catch (CborException ce) {
      throw new InternalError("Cbor Error" + ce.toString());
    }
  }
}

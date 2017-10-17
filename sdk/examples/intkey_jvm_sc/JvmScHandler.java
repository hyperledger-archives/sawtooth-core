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

package sawtooth.examples.jvmsc;

import com.google.protobuf.ByteString;
import com.google.protobuf.InvalidProtocolBufferException;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.cbor.CBORFactory;

import sawtooth.examples.jvmsc.JVMEntry;
import sawtooth.examples.jvmsc.JVMPayload;

import sawtooth.sdk.processor.State;
import sawtooth.sdk.messaging.Stream;
import sawtooth.sdk.processor.Utils;

import sawtooth.sdk.processor.TransactionHandler;
import sawtooth.sdk.processor.exceptions.InternalError;
import sawtooth.sdk.processor.exceptions.InvalidTransactionException;

import sawtooth.sdk.protobuf.Entry;
import sawtooth.sdk.protobuf.TpProcessRequest;
import sawtooth.sdk.protobuf.TpRegisterRequest;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;

import java.lang.ClassLoader;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

import java.security.ProtectionDomain;

import java.util.AbstractMap;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;


public class JvmScHandler implements TransactionHandler{

  private final Logger logger = Logger.getLogger(JvmScHandler.class.getName());
  Map<String, ByteString> cachedBytecode = new HashMap<String,ByteString>();
  private ObjectMapper mapper;

  class JvmClassLoader extends ClassLoader{
    public Class loadClassFromBytes(String name, byte[] bytes) {
      return defineClass(name, bytes, 0, bytes.length);
    }
  }

  public JvmScHandler() {
    CBORFactory factory = new CBORFactory();
    this.mapper = new ObjectMapper(factory);
  }

  @Override
  public String transactionFamilyName() {
    return "jvm_sc";
  }

  @Override
  public String getVersion() {
    return "1.0";
  }

  @Override
  public Collection<String> getNameSpaces() {
    ArrayList<String> namespaces = new ArrayList<String>();
    namespaces.add(Utils.hash512(this.transactionFamilyName().getBytes()).substring(0, 6));
    return namespaces;
  }

  /**
   * the method that returns an object from a byte[].
   */
  public static Object dataFromByteArray(byte[] data) throws IOException, ClassNotFoundException {
    ByteArrayInputStream input =  new ByteArrayInputStream(data);
    ObjectInputStream output = new ObjectInputStream(input);
    return output.readObject();
  }

  /**
   * the method that returnsa byte[] from an object.
   */
  public static byte[] dataToByteArray(Object data) throws IOException, ClassNotFoundException {
    ByteArrayOutputStream input =  new ByteArrayOutputStream();
    ObjectOutputStream output = new ObjectOutputStream(input);
    output.writeObject(data);
    return input.toByteArray();
  }

  /**
   * the method that stores bytecode in the state.
   */
  public void store(ByteString bytecode,ArrayList<String> methods,
                        State state) throws InvalidTransactionException, InternalError {
    // Calculate Address for bytecode
    String namespace = Utils.hash512(this.transactionFamilyName().getBytes()).substring(0, 6);
    String addr = namespace + Utils.hash512(bytecode.toByteArray());

    // Need to set {addr: {Bytecode: bytecode, Methods: Methods}}
    JVMEntry data = JVMEntry.newBuilder()
            .setBytecode(bytecode)
            .addAllMethods(methods)
            .build();
    Map.Entry<String, ByteString> entry =
        new AbstractMap.SimpleEntry<String, ByteString>(addr, data.toByteString());
    Collection<Map.Entry<String, ByteString>> entries =
        new ArrayList<Map.Entry<String, ByteString>>();
    entries.add(entry);
    Collection<String> response = state.set(entries);

    if (!response.contains(addr)) {
      throw new InvalidTransactionException("Bytecode was not stored succefully");
    }
  }

  /**
   * the method that runs the bytecode stored in the set.
   */

  public void run(String byteAddr, String method, List<String> parameters, State state)
      throws InvalidTransactionException, InternalError {
    try {
      Map<String, ByteString>  getResponse = new HashMap<String, ByteString>();

      // Check if bytecode has already been stored in the handler else get
      if (!cachedBytecode.containsKey(byteAddr)) {
        ArrayList<String> byteAddress = new ArrayList<String>();
        byteAddress.add(byteAddr);
        getResponse = state.get(byteAddress);
        cachedBytecode.put(byteAddr, getResponse.get(byteAddr));
      }

      // Get bytecode and method list
      JVMEntry bytecodeEntry = JVMEntry.parseFrom(cachedBytecode.get(byteAddr));
      List<String> methods = bytecodeEntry.getMethodsList(); //check type of
      ByteString bytecode = bytecodeEntry.getBytecode();

      // Check that given method is a valid option in the method list
      if (!methods.contains(method)) {
        throw new InvalidTransactionException("Tried to access invalid Method: " + method);
      }

      //Need to retrive parameters from context_id
      //Need to break apart the parameters thinking they will look like the following
      //["name,value","&name,value"]
      List<byte[]> args = new ArrayList<byte[]>();
      String[] temp;
      for (int i = 0; i < parameters.size(); i++) {
        temp = parameters.get(i).split(",");
        if (temp[0].substring(0,1).equals("&")) {
          ArrayList<String> address = new ArrayList<String>();
          address.add(temp[1]);
          getResponse = state.get(address);
          byte[] output = getResponse.get(temp[1]).toByteArray();
          if (output.length > 0) {
            HashMap updateMap = this.mapper.readValue(
                    getResponse.get(temp[1]).toByteArray(), HashMap.class);
            output = dataToByteArray(updateMap);
            args.add(output);
          } else {
            args.add(dataToByteArray("Not found"));
          }
        } else {
          args.add(temp[1].getBytes());
        }

      }

      //Load bytecode
      JvmClassLoader loader = new JvmClassLoader();
      Class loaded = loader.loadClassFromBytes(null, bytecode.toByteArray());

      //run bytecode method with the parameters, returns Map<string addr, byte[] value>
      Object classObject = loaded.newInstance();
      Method toInvoke = loaded.getMethod(method, ArrayList.class);
      Map<String, byte[]> output = new HashMap<String, byte[]>();
      try {
        output = (Map<String, byte[]>)toInvoke.invoke(classObject, new Object[] {args});
      } catch (InvocationTargetException ioe) {
        ioe.printStackTrace();
        throw new InvalidTransactionException("Something went wrong when invoking the method.");
      }

      // need to change Map<String, byte[]> to Map<String, ByteString>
      Map<String,ByteString> convertedOutput = new HashMap<String,ByteString>();
      String[] keys = output.keySet().toArray(new String[0]);

      for (int i = 0; i < keys.length; i++) {
        Object  toCbor = dataFromByteArray(output.get(keys[i]));
        convertedOutput.put(keys[i], ByteString.copyFrom(this.mapper.writeValueAsBytes(toCbor)));
      }

      //update context --set [{addr, value}, ....]
      Collection<Map.Entry<String, ByteString>> entries = convertedOutput.entrySet();
      Collection<String> setResponse = state.set(entries);

      // Check the response
      if (setResponse.size() != entries.size()) {
        throw new InvalidTransactionException("Not all Updates were set correctly");
      }
    } catch (InvalidProtocolBufferException ioe) {
      ioe.printStackTrace();
    } catch (InstantiationException ioe) {
      ioe.printStackTrace();
    } catch (IllegalAccessException ioe) {
      ioe.printStackTrace();
    } catch (NoSuchMethodException ioe) {
      ioe.printStackTrace();
    } catch (com.fasterxml.jackson.core.JsonProcessingException ioe) {
      ioe.printStackTrace();
    } catch (ClassNotFoundException ioe) {
      ioe.printStackTrace();
    } catch (IOException ioe) {
      ioe.printStackTrace();
    }

  }

  @Override
  public void apply(TpProcessRequest transactionRequest, State state)
      throws InvalidTransactionException, InternalError {
    try {
      JVMPayload payload = JVMPayload.parseFrom(transactionRequest.getPayload());
      String verb = payload.getVerb();
      logger.info(payload.toString());
      if (verb.length() == 0) {
        throw new InvalidTransactionException("Verb is required and must be store or run");
      }

      if (!Arrays.asList("store", "run").contains(verb)) {
        throw new InvalidTransactionException("Verb must be store or run, not " + verb);
      }

      if (verb.equals("store")) {
        ByteString bytecode = payload.getBytecode();
        ArrayList<String> methods = new ArrayList<String>();
        for (String method: payload.getMethodsList()) {
          methods.add(method);
        }
        this.store(bytecode, methods, state);
      }

      if (verb.equals("run")) {
        String byteAddr = payload.getByteAddr();
        String method = payload.getMethod();
        List<String> parameters = payload.getParametersList();
        this.run(byteAddr, method, parameters, state);
      }
    } catch (IOException ioe) {
      ioe.printStackTrace();
      throw new InternalError("State error");
    }

  }

}

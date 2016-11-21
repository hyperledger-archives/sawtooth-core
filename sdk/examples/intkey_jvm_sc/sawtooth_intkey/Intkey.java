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
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.nio.charset.Charset;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import javax.xml.bind.DatatypeConverter;

public class Intkey {

  /**
   * the method that sets the intkey key value pair.
   */
  public Map<String, byte[]> set(ArrayList<byte[]> args) throws Exception {

    if (args.size() < 3) {
      throw new Exception("Wrong number of args. Should have 3.");
    }
    if (!(getString(args.get(2)).equals("Not found"))) {

      HashMap<String, Integer> check = (HashMap<String, Integer>) dataFromByteArray(args.get(2));
      if (check.containsKey(getString(args.get(0)))) {
        throw new Exception("Cannot reset a key.");
      }
    }

    Map<String,byte[]> output = new HashMap<String,byte[]>();
    Map<String,Integer> data = new HashMap<String,Integer>();
    String namespace = hash512("intkey".getBytes()).substring(0,6);;
    String addr = namespace + hash512(args.get(0));
    data.put(getString(args.get(0)), Integer.parseInt(getString(args.get(1))));

    byte[] value = dataToByteArray(data);
    output.put(addr, value);
    return output;
  }

  /**
   * the method that inc the value of the key.
   */
  public Map<String, byte[]> inc(ArrayList<byte[]> args) throws Exception {
    if (args.size() < 3) {
      throw new Exception("Wrong number of args. Should have 3.");
    }
    HashMap<String, Integer> check = (HashMap<String, Integer>) dataFromByteArray(args.get(1));
    if (!check.containsKey(getString(args.get(0)))) {
      throw new Exception("Cannot reset a key.");
    }

    Map<String,byte[]> output = new HashMap<String,byte[]>();
    Map<String, Integer> data = new HashMap<String,Integer>();
    String namespace = hash512("intkey".getBytes()).substring(0,6);
    String addr = namespace + hash512(args.get(0));

    Integer val = check.get(getString(args.get(0)));

    Integer increment = Integer.parseInt(getString(args.get(2)));

    val = val + increment;

    data.put(getString(args.get(0)), val);
    byte[] toStore = dataToByteArray(data);
    output.put(addr,toStore);
    return output;
  }

  /**
   * the method that dec the value of the key.
   */
  public Map<String, byte[]> dec(ArrayList<byte[]> args) throws Exception {
    if (args.size() < 3) {
      throw new Exception("Wrong number of args. Should have 3.");
    }

    HashMap<String, Integer> check = (HashMap<String, Integer>) dataFromByteArray(args.get(1));
    if (!check.containsKey(getString(args.get(0)))) {
      throw new Exception("Key does not exist");
    }

    Map<String,byte[]> output = new HashMap<String,byte[]>();
    Map<String, Integer> data = new HashMap<String,Integer>();
    String namespace = hash512("intkey".getBytes()).substring(0,6);
    String addr = namespace + hash512(args.get(0));

    Integer val = check.get(getString(args.get(0)));

    Integer decrement = Integer.parseInt(getString(args.get(2)));

    val = val - decrement;

    data.put(getString(args.get(0)), val);
    byte[] toStore = dataToByteArray(data);
    output.put(addr, toStore);
    return output;
  }

  /**
   * the method that hashes data to get the address.
   */
  public static String hash512(byte[] data) {
    String result = null;
    try {
      MessageDigest messageDigest = MessageDigest.getInstance("SHA-512");

      messageDigest.update(data);


      byte[] mdBytes = messageDigest.digest();
      result = DatatypeConverter.printHexBinary(mdBytes).toLowerCase();

    } catch (NoSuchAlgorithmException nsae) {
      nsae.printStackTrace();
    }
    return result;
  }

  /**
   * the method takes a byte[] and returns a string.
   */
  public static String getString(byte[] data) {
    return new String(data, Charset.forName("UTF-8"));
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
   * the method that returns an object from a byte[].
   */
  public static byte[] dataToByteArray(Object data) throws IOException, ClassNotFoundException {
    ByteArrayOutputStream input =  new ByteArrayOutputStream();
    ObjectOutputStream output = new ObjectOutputStream(input);
    output.writeObject(data);
    return input.toByteArray();
  }
}


import java.io.ByteArrayInputStream;
import java.io.ObjectInputStream;
import java.nio.charset.Charset;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import javax.xml.bind.DatatypeConverter;

public class Intkey{

  /**
   * the method that sets the intkey key value pair.
   */
  public Map<String, byte[]> set(ArrayList<byte[]> args) throws Exception {

    if (args.size() < 3) {
      throw new Exception("Wrong number of args. Should have 3.");
    }

    if (!(getString(args.get(2)).equals("Not found"))) {
      throw new Exception("Cannot reset a key.");
    }

    Map<String,byte[]> output = new HashMap<String,byte[]>();
    Map<String,Integer> data = new HashMap<String,Integer>();
    String namespace = hash512("intkey".getBytes()).substring(0,6);;
    String addr = namespace + hash512(args.get(0));
    data.put(getString(args.get(0)), Integer.parseInt(getString(args.get(1))));

    byte[] value = data.toString().getBytes();
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

    Map<String,byte[]> output = new HashMap<String,byte[]>();
    Map<String, Integer> data = new HashMap<String,Integer>();
    String namespace = hash512("intkey".getBytes()).substring(0,6);
    String addr = namespace + hash512(args.get(0));

    // test
    String value = getString(args.get(1)).split("=")[1];
    Integer val = Integer.parseInt(value.substring(0,(value.length() - 1)));

    Integer increment = Integer.parseInt(getString(args.get(2)));

    val = val + increment;

    data.put(addr, val);
    byte[] toStore = data.toString().getBytes();
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

    Map<String,byte[]> output = new HashMap<String,byte[]>();
    Map<String, Integer> data = new HashMap<String,Integer>();
    String namespace = hash512("intkey".getBytes()).substring(0,6);
    String addr = namespace + hash512(args.get(0));

    String value = getString(args.get(1)).split("=")[1];
    Integer val = Integer.parseInt(value.substring(0,(value.length() - 1)));

    Integer decrement = Integer.parseInt(getString(args.get(2)));

    val = val - decrement;

    data.put(addr, val);
    byte[] toStore = data.toString().getBytes();
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
}

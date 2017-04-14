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

import java.nio.charset.Charset;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import javax.xml.bind.DatatypeConverter;


public class Utils {

  /**
   * Create a sha-512 hash of a byte array.
   *
   * @param data a byte array which the hash is created from
   * @return result a lowercase HexDigest of a sha-512 hash
   */
  public static String hash512(byte[] data) {
    String result = null;
    try {
      MessageDigest messageDigest = MessageDigest.getInstance("SHA-512");

      messageDigest.update(data);


      byte[] digest = messageDigest.digest();
      result = DatatypeConverter.printHexBinary(digest).toLowerCase();

    } catch (NoSuchAlgorithmException nsae) {
      nsae.printStackTrace();
    }
    return result;
  }

  /**
   * Helper function. for dealing with Strings that come in via
   * protobuf ByteString encoded cbor.
   *
   * @param fromCbor byte array from a String that came in via cbor
   * @return a UTF-8 representation of the byte array
   */
  public static String stringByteArrayToString(byte[] fromCbor) {
    return new String(fromCbor, Charset.forName("UTF-8"));
  }


}

/* Copyright 2017 Intel Corporation
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

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.lang.String;
import java.math.BigInteger;
import java.util.ArrayList;

import static org.junit.Assert.assertEquals;

import org.junit.Before;
import org.junit.Test;

import org.bitcoinj.core.ECKey;

import sawtooth.sdk.client.Signing;


public class SigningTest {

  private static ArrayList<String> PrivateKeys = new ArrayList();
  private static ArrayList<String> PublicKeys = new ArrayList();

  @Before
  public void setUp() throws FileNotFoundException, IOException{
    BufferedReader privateKeyReader = new BufferedReader(
        new FileReader(this.getClass().getResource("private_keys.txt").getFile()));

    String linePrivate = privateKeyReader.readLine();
    while(linePrivate != null) {
      PrivateKeys.add(linePrivate);
      linePrivate = privateKeyReader.readLine();
    }

    BufferedReader publicKeyReader = new BufferedReader(
        new FileReader(this.getClass().getResource("public_keys.txt").getFile()));
    String linePublic = publicKeyReader.readLine();
    while(linePublic != null) {
      PublicKeys.add(linePublic);
      linePublic = publicKeyReader.readLine();
    }
  }


  @Test
  public void publicKeyFromPrivate() {
    for(int i=0; i < PrivateKeys.size(); i++) {
      String privateKeyWif = PrivateKeys.get(i);
      ECKey privateKey = Signing.readWif(privateKeyWif);

      String expectedPublicKey = PublicKeys.get(i);
      String calculatedPublicKey = Signing.getPublicKey(privateKey);

      assertEquals("The calculated public key must equal sawtooth_signing's calculation",
          expectedPublicKey,
          calculatedPublicKey);
    }

  }


}
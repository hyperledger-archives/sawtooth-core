package sawtooth.sdk.client.sawtooth.sdk.client;

import org.bitcoinj.core.DumpedPrivateKey;
import org.bitcoinj.core.ECKey;
import org.bitcoinj.core.NetworkParameters;
import org.bitcoinj.core.Sha256Hash;
import org.bitcoinj.core.Utils;

import java.security.SecureRandom;


public class Signing {

  private static final NetworkParameters MAINNET = org.bitcoinj.params.MainNetParams.get();

  public static ECKey readWif(String wif) {
    return DumpedPrivateKey.fromBase58(MAINNET, wif).getKey();
  }

  public static ECKey generatePrivateKey(SecureRandom random) {
    return new ECKey(random);
  }

  public static String getPublicKey(ECKey privateKey) {
    return "03" + privateKey.getPublicKeyAsHex();
  }

  /**
   * Returns a bitcoin-style 64-byte compact signature.
   * @param privateKey the private key with which to sign
   * @param data the data to sign
   * @return String the signature
   */
  public static String sign(ECKey privateKey, byte[] data) {
    Sha256Hash hash = Sha256Hash.of(data);
    ECKey.ECDSASignature sig = privateKey.sign(hash);

    byte[] csig = new byte[64];

    System.arraycopy(Utils.bigIntegerToBytes(sig.r, 32), 0, csig, 0, 32);
    System.arraycopy(Utils.bigIntegerToBytes(sig.s, 32), 0, csig, 32, 32);

    return Utils.HEX.encode(csig);
  }
}

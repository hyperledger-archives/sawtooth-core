package sawtooth.sdk.processor.exceptions;

/**
 * Base Exception for exceptions that included opaque extended data that must be
 * returned on the response.
 */
public class SawtoothException extends Exception {
  private final byte[] extendedData;

  /**
   * Creates an exception.
   * @param message the message to return on the response
   */
  public SawtoothException(final String message) {
    super(message);
    this.extendedData = null;
  }

  /**
   * Creates an exception with extended data.
   * @param message the message to returned on the response
   * @param extendedData opaque, application-specific encoded data to be
   *     returned on the response
   */
  public SawtoothException(final String message, final byte[] extendedData) {
    super(message);
    this.extendedData = extendedData;
  }

  /**
   * The extended data associated with this exception.
   * @return opaque, application-specific encoded data
   */
  public byte[] getExtendedData() {
    return extendedData;
  }
}

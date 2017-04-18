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

package sawtooth.sdk.messaging;

import com.google.protobuf.ByteString;

import sawtooth.sdk.processor.exceptions.ValidatorConnectionError;

import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;

public class FutureError implements Future{

  /**
   * Constructor.
   */
  public FutureError() {
  }

  /**
   * Always raises ValidatorConnectionError.
   */
  public ByteString getResult() throws InterruptedException,
      ValidatorConnectionError {
    throw new ValidatorConnectionError();
  }

  /**
   * Always raises ValidatorConnectionError.
   */
  public ByteString getResult(long time) throws InterruptedException,
     ValidatorConnectionError {
    throw new ValidatorConnectionError();
  }

  /**
   * Always raises ValidatorConnectionError.
   */
  public void setResult(ByteString byteString) throws ValidatorConnectionError {
    throw new ValidatorConnectionError();
  }

  /**
   * Always raises ValidatorConnectionError.
   */
  public boolean isDone() throws ValidatorConnectionError {
    throw new ValidatorConnectionError();
  }

}

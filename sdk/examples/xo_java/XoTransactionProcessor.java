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

package sawtooth.examples.xo;

import sawtooth.examples.xo.XoHandler;
import sawtooth.sdk.processor.TransactionProcessor;

public class XoTransactionProcessor {
  /**
   * the method that runs a Thread with a TransactionProcessor in it.
   */
  public static void main(String[] args) {
    TransactionProcessor transactionProcessor = new TransactionProcessor(args[0]);
    transactionProcessor.addHandler(new XoHandler());
    Thread thread = new Thread(transactionProcessor);
    thread.start();
  }
}

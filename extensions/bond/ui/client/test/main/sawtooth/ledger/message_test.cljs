; Copyright 2016 Intel Corporation
;
; Licensed under the Apache License, Version 2.0 (the "License");
; you may not use this file except in compliance with the License.
; You may obtain a copy of the License at
;
;     http://www.apache.org/licenses/LICENSE-2.0
;
; Unless required by applicable law or agreed to in writing, software
; distributed under the License is distributed on an "AS IS" BASIS,
; WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
; See the License for the specific language governing permissions and
; limitations under the License.
; ------------------------------------------------------------------------------

(ns sawtooth.ledger.message-test
   (:require [cljs.test :refer-macros [deftest testing is async use-fixtures]]
             [sawtooth.ledger.message :as msg]))


(deftest test-make-transaction
  (testing "with no dependencies"
    (let [update {:UpdateType "/mktplace.transactions.ParticipantUpdate/Register"
                  :Name "Bob"
                  :Description "A user"}
          txn (msg/make-transaction "/my-txn-family" update)]
      (is (= "/my-txn-family" (:TransactionType txn)))
      (is (not (nil? (:Nonce txn))))
      (is (= [] (:Dependencies txn)))
      (is (= update (:Update txn))))))

(deftest test-to-signable
  (testing "to signable should sort keys"
    (let [m {:d 1 :a 5 :m {:d 1 :a 5} :v [{:d 1 :a 5} {:d 1 :a 5}]}
          signed (msg/->signable m)]
      (is (= (keys signed) [:a :d :m :v]))
      (is (= (keys (:m signed)) [:a :d]))
      (is (= (keys (get-in signed [:v 0])) [:a :d]))
      (is (= (keys (get-in signed [:v 1])) [:a :d]))
      ))
  (testing "should not rearrange strings"
    (let [m {:m {:d "bar"} :d "ofo" :v ["argle" "bargle"]}
          signed (msg/->signable m)]
      (is (= (keys signed) [:d :m :v]))
      (is (= (:d signed) "ofo"))
      (is (= (get-in signed [:v 0]) "argle"))
      (is (= (get-in signed [:m :d] "bar"))))))

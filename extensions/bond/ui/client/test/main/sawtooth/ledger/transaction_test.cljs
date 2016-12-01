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

(ns sawtooth.ledger.transaction-test
  (:require [cljs.test :refer-macros [deftest testing is async use-fixtures]]
            [cljs.core.async :as async :refer [put! alts!]]
            [taoensso.timbre :as log :include-macros]
            [sawtooth.test-common :as tcomm :refer-macros [with-reset <*]]
            [sawtooth.http :as http]
            [sawtooth.ledger.message :as msg]
            [sawtooth.ledger.transaction :as txn
             :refer-macros [chain-transactions send-chained-transactions]])
  (:require-macros [cljs.core.async.macros :refer [go]]))


(defn- mock-json-xhr
  ([start-id submitted-content] (mock-json-xhr start-id submitted-content #{}))
  ([start-id submitted-content failure-ids]
   (let [id (atom start-id)]
     (fn [_ _ body ch]
       (swap! submitted-content conj body)
       (let [next-id (swap! id inc)]
         (put! ch
              (if-not (failure-ids next-id)
                {:status 200
                 :body (str next-id)}
                {:status 500
                 :body ""})))))))

(def error-json-xhr (mock-json-xhr 0 (atom {}) (constantly true)))

(defn- mock-signing [_ txn-family txn]
  (let [ch (async/chan)]
    (put! ch {:__TYPE__ txn-family :Transaction txn})
    ch))

(deftest chain-transactions-existing-txn
  (async done
    (testing "sending a single txn that is already an id"
      (go
      (let [submitted-details (atom [])
            existing-obj-id "exiting id" ]
        (with-reset [http/json-xhr (mock-json-xhr 0 submitted-details)
                      msg/sign mock-signing]
          (let [ch (chain-transactions
                     "my-wallet-id"
                     "my-msg-type"
                     [_ existing-obj-id])
                [final-id txn]  (<* ch 250)]
            (is (= "exiting id" final-id))
            (is (= [] @submitted-details))
            (done))))))))

(deftest chain-transactions-single-txn
  (async done
    (testing "send chained transactions with a single entry"
      (go
        (let [submitted-details (atom [])]
          (with-reset [http/json-xhr (mock-json-xhr 0 submitted-details)
                       msg/sign mock-signing]
            (let [ch (chain-transactions
                       "my-wallet-id"
                       "my-msg-type"
                       [_ (msg/make-transaction "/txn-family" {:UpdateType "/mytxn" :count 1 })])
                  [final-id txn] (<* ch 250)]
              (is (= "1" final-id))
              (is (= {:UpdateType "/mytxn" :count 1}
                     (get txn :Update)))
              (is (= 1 (count @submitted-details)))
              (is (= {:UpdateType "/mytxn" :count 1}
                     (-> @submitted-details
                         first
                         (get-in [:transaction :Transaction :Update]))))
              (is (nil? (-> @submitted-details first :annotations)))
              (done))))))))

(deftest chain-transactions-multiple
  (async done
    (testing "send multiple chained transactions with references"
      (go
        (let [submitted-details (atom [])]
          (with-reset [http/json-xhr (mock-json-xhr 0 submitted-details)
                       msg/sign mock-signing]
            (let [ch (chain-transactions
                       "my-wallet-id"
                       "my-msg-type"
                       [first-id (msg/make-transaction "/txn-family" {:UpdateType "/First"})
                        _ (msg/make-transaction "/txn-family" {:UpdateType "/Second" :creator first-id})])
                  [final-id final-txn] (<* ch 250)]
              (is (= "2" final-id))
              (is (= {:UpdateType "/Second" :creator "1"}
                     (get final-txn :Update)))
              (is (= 2 (count @submitted-details)))
              (is (= {:UpdateType "/First"}
                     (-> @submitted-details
                         first
                         (get-in [:transaction :Transaction :Update]))))
              (is (= {:UpdateType "/Second" :creator "1"}
                     (-> @submitted-details
                         second
                         (get-in [:transaction :Transaction :Update]))))
              (done))))))))

(deftest chain-transactions-multiple-with-existing
  (async done
    (testing "send multiple chained transactions with references"
      (go
        (let [submitted-details (atom [])]
          (with-reset [http/json-xhr (mock-json-xhr 10 submitted-details)
                       msg/sign mock-signing]
            (let [ch (chain-transactions
                       "my-wallet-id"
                       "my-msg-type"
                       [first-id "number1"
                        _ (msg/make-transaction "/txn-family" {:UpdateType "/Second" :creator first-id})])
                  [final-id final-txn] (<* ch 250)]
              (is (= "11" final-id))
              (is (= {:UpdateType "/Second" :creator "number1"}
                     (get final-txn :Update)))

              (is (= 1 (count @submitted-details)))
              (is (= {:UpdateType "/Second" :creator "number1"}
                     (-> @submitted-details
                         first
                         (get-in [:transaction :Transaction :Update]))))
              (done))))))))

(deftest chain-transactions-with-annotations
  (async done
    (testing "send chained transactions with a single entry"
      (go
        (let [submitted-details (atom [])]
          (with-reset [http/json-xhr (mock-json-xhr 0 submitted-details)
                       msg/sign mock-signing]
            (let [ch (chain-transactions
                       "my-wallet-id"
                       "my-msg-type"
                       [_ [(msg/make-transaction "/txn-family" {:UpdateType "/mytxn" :count 1 })
                           {:creator "alice"} ]])
                  [final-id final-txn] (<* ch 250)]
              (is (= "1" final-id))
              (is (= {:UpdateType "/mytxn" :count 1}
                     (get final-txn :Update)))

              (is (= 1 (count @submitted-details)))
              (is (= {:UpdateType "/mytxn" :count 1}
                     (-> @submitted-details
                         first
                         (get-in [:transaction :Transaction :Update]))))
              (is (= {:creator "alice"}
                     (-> @submitted-details
                         first
                         :annotations)))
              (done))))))))

(deftest chain-transactions-first-fail
  (async done
    (testing "send multiple chained transactions with references"
      (go
        (let [submitted-details (atom [])]
          (with-reset [http/json-xhr error-json-xhr
                       msg/sign mock-signing]
            (let [ch (chain-transactions "my-wallet-id" "my-msg-type"
                       [first-id (msg/make-transaction "/txn-family" {:UpdateType "/First"})
                        last-id (msg/make-transaction "/txn-family" {:UpdateType "/Second"
                                                                     :creator first-id})])
                  [final-id final-txn] (<* ch 250)]
              (is (:error? final-id))
              (is (= {:UpdateType "/First"}
                     (:Update final-txn)))
              (done))))))))

(deftest chain-transactions-with-arbitrary-length
  (async done
    (testing "send an arbitrary number of transactions with a list"
      (go
        (let [submitted-details (atom [])]
          (with-reset [http/json-xhr (mock-json-xhr 0 submitted-details)
                       msg/sign mock-signing]
            (let [ch (chain-transactions "my-wallet-id" "my-msg-type"
                       [first-id (msg/make-transaction "/txn-family" {:UpdateType "/First"})
                        list-ids (list (msg/make-transaction "/txn-family" {:UpdateType "/Second"
                                                                            :creator first-id})
                                       (msg/make-transaction "/txn-family" {:UpdateType "/Third"
                                                                            :creator first-id}))])
                  [final-ids final-txns] (<* ch 250)]
              (is (= 3 (count @submitted-details)))
              (is (= ["2" "3"] final-ids))
              (is (= 2 (count final-txns)))
              (is (= [{:UpdateType "/Second" :creator "1"}
                      {:UpdateType "/Third" :creator "1"}]
                     (mapv :Update final-txns)))
              (done))))))))

#_(deftest chain-transactions-with-arbitrary-length-empty-list
  (async done
    (testing "send an arbitrary number of transactions with a list"
      (go
        (let [submitted-details (atom [])]
          (with-reset [http/json-xhr (mock-json-xhr 0 submitted-details)
                       msg/sign mock-signing]
            (let [ch (chain-transactions "my-wallet-id" "my-msg-type"
                       [first-id (msg/make-transaction "/txn-family" {:UpdateType "/First"})
                        list-ids ()])
                  [final-id final-txn] (<* ch 250)]
              (is (= 1 (count @submitted-details)))
              (is (= "1" final-id))
              (is (= {:UpdateType "/First" :creator "1"}
                     (:Update final-txn)))
              (done))))))))

(deftest chain-transactions-with-arbitrary-length-with-annotations
  (async done
    (testing "send an arbitrary number of transactions with a list"
      (go
        (let [submitted-details (atom [])]
          (with-reset [http/json-xhr (mock-json-xhr 0 submitted-details)
                       msg/sign mock-signing]
            (let [ch (chain-transactions "my-wallet-id" "my-msg-type"
                       [first-id (msg/make-transaction "/txn-family" {:UpdateType "/First"})
                        list-ids (list [(msg/make-transaction "/txn-family" {:UpdateType "/Second"
                                                                             :creator first-id})
                                        {:some-id "something"}]
                                       (msg/make-transaction "/txn-family" {:UpdateType "/Third"
                                                                            :creator first-id}))])
                  [final-ids final-txns] (<* ch 250)]
              (is (= 3 (count @submitted-details)))
              (is (= ["2" "3"] final-ids))
              (is (= 2 (count final-txns)))
              (is (= [{:UpdateType "/Second" :creator "1"}
                      {:UpdateType "/Third" :creator "1"}]
                     (mapv :Update final-txns)))
              (is (= {:some-id "something"}
                     (-> @submitted-details
                         second
                         :annotations)))
              (done))))))))

(deftest chain-transactions-with-arbitrary-length-with-errors
  (async done
    (testing "send an arbitrary number of transactions with a list, with an error"
      (go
        (let [submitted-details (atom [])]
          (with-reset [http/json-xhr (mock-json-xhr 0 submitted-details #{2})
                       msg/sign mock-signing]
            (let [ch (chain-transactions "my-wallet-id" "my-msg-type"
                       [first-id (msg/make-transaction "/txn-family" {:UpdateType "/First"})
                        list-ids (list (msg/make-transaction "/txn-family" {:UpdateType "/Second"
                                                                            :creator first-id})
                                       (msg/make-transaction "/txn-family" {:UpdateType "/Third"
                                                                            :creator first-id}))])
                  [final-ids final-txns] (<* ch 250)]
              (is (= 3 (count @submitted-details)))
              (is (= [{:error? true
                       :message "an unknown server error occurred."}
                      "3"]
                     final-ids))
              (is (= 2 (count final-txns)))
              (is (= [{:UpdateType "/Second" :creator "1"}
                      {:UpdateType "/Third" :creator "1"}]
                     (mapv :Update final-txns)))
              (done))))))))

(deftest send-chained-transaction-with-notifications
  (async done
    (testing "send transactions with success/failure"
      (go
        (let [submitted-details (atom [])
              success (atom nil)]
          (with-reset [http/json-xhr (mock-json-xhr 0 submitted-details)
                       msg/sign mock-signing
                       txn/on-transaction-success #(reset! success [%1 %2])]
            (let [ch (send-chained-transactions "my-wallet-id" "my-msg-type"
                       [first-id (msg/make-transaction "/txn-family" {:UpdateType "/first"})
                        _ (msg/make-transaction "/txn-family" {:UpdateType "/Second"
                                                               :creator first-id})]
                       nil)
                  final-id  (<* ch 250)]
              (is (= "2" final-id))

              (let [[txn done-fn] @success]
                (is (nil? done-fn))
                (is (= {:UpdateType "/Second" :creator "1"}
                       (:Update txn))))

              (done))))))))

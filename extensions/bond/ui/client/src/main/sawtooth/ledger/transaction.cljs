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

(ns sawtooth.ledger.transaction
  (:refer-clojure :exclude [send])
  (:require [cljs.core.async :as async :refer [put! take!]]
            [goog.string :as gstring]
            [taoensso.timbre :as log :include-macros]
            [clojure.string :refer [join]]
            [sawtooth.config :refer [base-url]]
            [sawtooth.state :refer [state-change-ch notification-action]]
            [sawtooth.http :as http]
            [sawtooth.ledger.message :as msg])
  (:require-macros [cljs.core.async.macros :refer [go]]))

(def ^:const TRANSACTIONS_ENDPOINT (str base-url "/api/ledger/transactions"))

(defn- update-type [txn]
  (if-let [type-str (get-in txn [:Update :UpdateType])]
    type-str
    (join ", " (map :UpdateType (get txn :Updates)))))

(defn- vectorize [x]
  (if (vector? x) x [x nil]))

(defn- unwrap-vec [v]
  (if (vector? v) (first v) v))

(defn on-transaction-success [txn on-done-fn]
  (put! state-change-ch
        (notification-action
          {:type :info
           :title "Transaction Submitted"
           :message (gstring/format "Your %s transaction has been
                                    submitted to the validator."
                                    (update-type txn))}))
  (when on-done-fn
    (on-done-fn)))

(defn on-transaction-failure [txn failure-info]
  (put! state-change-ch
        (notification-action
          {:type :error
           :title "Unable to Submit Transaction!"
           :message (gstring/format
                      "Unable to submit a %s transaction at this time:\n%s"
                      (update-type txn)
                      (:message failure-info))})))

(defn send
  "Sends a transaction, returning a channel that will contain the
  resulting transaction id, or :error if it fails."
  ([signing-identity msg-type txn] (send signing-identity msg-type txn nil))
  ([signing-identity msg-type txn annotations]
   {:pre [(not (nil? signing-identity))
          (string? msg-type)
          (map? txn)
          (or (nil? annotations) (map? annotations))]}
   (let [res-ch (async/chan 1 (map (fn [{:keys [status body]}]
                                     (cond
                                       (and (= status 200) (= (:statusCode body) 400))
                                       {:error? true
                                        :message (gstring/format
                                                   "%s.\n%s."
                                                   (:errorTypeMessage body)
                                                   (:errorMessage body))}

                                       (= status 200)
                                       body

                                       :else {:error? true
                                              :message "an unknown server error occurred."}))))
        signed-txn-ch (msg/sign signing-identity msg-type txn)]
    (go
      (let [signed-txn (<! signed-txn-ch)]
        (http/json-xhr :post
                       TRANSACTIONS_ENDPOINT
                       {:transaction signed-txn
                        :annotations annotations}
                       res-ch)))
    res-ch)))

(defn send-transaction
  "Sends a transaction"
  ([signing-identity msg-type txn]
   (send-transaction signing-identity msg-type txn nil nil))

  ([signing-identity msg-type txn annotations-or-on-done-fn]
   (let [annotations (if-not (fn? annotations-or-on-done-fn) annotations-or-on-done-fn nil)
         on-done-fn (if (fn? annotations-or-on-done-fn) annotations-or-on-done-fn nil)]
     (send-transaction signing-identity msg-type txn annotations on-done-fn)))

  ([signing-identity msg-type txn annotations on-done-fn]
   {:pre [(not (nil? signing-identity))
          (string? msg-type)
          (map? txn)
          (or (nil? annotations) (map? annotations))
          (or (nil? on-done-fn) (fn? on-done-fn))]}
   (take! (send signing-identity msg-type txn annotations)
         (fn [result]
           (if-not (:error? result)
             (on-transaction-success txn on-done-fn)
             (on-transaction-failure txn result))))))

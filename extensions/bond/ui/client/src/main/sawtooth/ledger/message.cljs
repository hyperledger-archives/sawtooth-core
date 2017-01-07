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
(ns sawtooth.ledger.message
  (:require [cljs.core.async :as async :refer [<! >!]]
            [sawtooth.vendor :refer [bitcoin Ratio]]
            [sawtooth.math :as math])
  (:require-macros [cljs.core.async.macros :refer [go]]))

(def ^:dynamic *ratios* (atom #{:Ratio}))

(defn set-ratio-fields! [field-set]
  (reset! *ratios* (set field-set)))

(defn reset-ratio-fields! []
  (reset! *ratios* #{:Ratio}))

(defn- seconds-since-epoch []
  (math/floor (/ (.now js/Date) 1000)))

(defn- sort-by-keys [m xform]
  (->> m
    (map (fn [[k v]] [k (cond (map? v)
                              (sort-by-keys v xform)
                              (vector? v)
                              (mapv #(if (map? %)
                                       (sort-by-keys % xform)
                                       %)
                                    v)
                              :default
                              (xform k v))]))
    (into (sorted-map-by compare))) )

(defn ->signable [m]
  (sort-by-keys m #(if (@*ratios* %1) (Ratio. %2) %2)))

(defn signable->map [signable-obj]
  (sort-by-keys signable-obj #(if (instance? Ratio %2) (.-n %2) %2)))

(defprotocol Signee
  (do-sign
    [self m k]
    "Signs the given map and assoc's the resulting signature at the given key.
    Returns the signed map on a channel")

  (public-key
    [self]
    "Returns the public key associated with the with the Signee"))

(defn- sign-transaction [signee txn]
  (do-sign signee txn :Signature))

(defn- sign-message [signee msg]
  (do-sign signee msg :__SIGNATURE__))

(defn sign [signee msg-type txn]
  {:pre [(satisfies? Signee signee)]}
  (let [pub-key (public-key signee)
        txn (cond-> txn
              (not (:Nonce txn)) (assoc :Nonce (seconds-since-epoch))
              (not (:PublicKey txn)) (assoc :PublicKey pub-key))]
    (go
      (let [signed-txn (<! (sign-transaction signee txn))
            msg {:Transaction signed-txn
                 :__TYPE__ msg-type
                 :__NONCE__ (seconds-since-epoch)}
            signed-msg (<! (sign-message signee msg))]
        signed-msg))))

(defn make-transaction
  "Makes a transaction body for the given update."
  ([txn-type txn-update]
   (make-transaction txn-type txn-update []))
  ([txn-type txn-update dependencies]
   {:pre [(string? txn-type)
          (or (vector? txn-update)(map? txn-update))
          (vector? dependencies)]}
   (cond-> {:TransactionType txn-type
            :Nonce (seconds-since-epoch)
            :Dependencies dependencies}
     (vector? txn-update)
     (assoc :Updates txn-update)
     (map? txn-update)
     (assoc :Update txn-update))))

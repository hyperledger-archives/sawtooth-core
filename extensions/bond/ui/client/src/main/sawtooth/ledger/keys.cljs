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
(ns sawtooth.ledger.keys
  (:require [cljs.core.async :as async]
            [sawtooth.ledger.message :as msg
             :refer [->signable signable->map]]
            [sawtooth.vendor :refer [bitcoin]]
            [sawtooth.store :refer [get-data save-data! remove-data!]]))


(defn- direct-sign [ec-pair m field]
    (let [signable-obj (-> m
                           ->signable
                           (dissoc field))
          signature (.sign bitcoin ec-pair (clj->js signable-obj))]
      (-> signable-obj
          (assoc field signature)
          signable->map)))

(defrecord KeyPair [ec-pair]

  msg/Signee

  (do-sign [_ m field]
    (async/to-chan [(direct-sign ec-pair m field)]))

  (public-key [_]
    (.publicKeyHex bitcoin ec-pair)))

(defn random-key-pair
  "Creates a random key pair."
  []
  (KeyPair. (.. bitcoin -ECPair makeRandom)))

(defn wif->key-pair
  "Takes an encoded WIF key and returns a key pair."
  [wif-str]
  (KeyPair. (.. bitcoin -ECPair (fromWIF wif-str))))

(defn key-pair->wif
  "Takes a key pair and returns a WIF encoded string."
  [key-pair]
  (.toWIF (:ec-pair key-pair)))

(defn address
  "Returns the address associated with the given key pair."
  [key-pair]
  (when key-pair
    (.getAddress (:ec-pair key-pair))))

(defn get-key-pair
  "Returns a key-pair from cookie/local storage"
  []
  (when-let [wif (get-data :wif-key)]
    (wif->key-pair wif)))

(defn save-wif!
  "Saves wif-key to a cookie or local storage"
  [wif-key]
  (save-data! :wif-key wif-key))

(defn clear-wif!
  "Removes the WIF key from storage."
  []
  (remove-data! :wif-key))

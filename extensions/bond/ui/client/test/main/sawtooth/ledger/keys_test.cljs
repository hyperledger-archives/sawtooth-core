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

(ns sawtooth.ledger.keys-test
  (:require [cljs.test
             :refer-macros [deftest testing is async use-fixtures]]
            [sawtooth.ledger.keys :as ledger-keys]
            [sawtooth.ledger.message :as msg]
            [sawtooth.test-common
             :refer [is-phantom?]
             :refer-macros [<*]]
            [cljs.core.async :as async])
  (:require-macros [cljs.core.async.macros :refer [go]]))


(defn- base64? [s]
  (when (string? s)
    (re-matches #"([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{4}|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)$" s)))

(defn- base58? [s]
  (when (string? s)
    (re-matches #"^[5KL][1-9A-HJ-NP-Za-km-z]{50,51}$" s)))

(deftest creates-a-signature
  (testing "Creates a signature and returns it on a channel"
    (when-not is-phantom?
      (async done
        (go
          (let [k (ledger-keys/random-key-pair)
                signed-obj (<* (msg/do-sign k {:x 1 :y 2} :signature) 250)
                signature (:signature signed-obj)]
            (is (base64? signature))
            (is (= {:x 1 :y 2} (select-keys signed-obj [:x :y])))
            (done)))))))

(deftest to-from-wif
  (testing "Round trip conversion to and from WIF"
    (when-not is-phantom?
      (let [k (ledger-keys/random-key-pair)]
        (is (base58? (ledger-keys/key-pair->wif k)))
        (is (= (ledger-keys/address k)
               (-> k
                   ledger-keys/key-pair->wif
                   ledger-keys/wif->key-pair
                   ledger-keys/address)))))))

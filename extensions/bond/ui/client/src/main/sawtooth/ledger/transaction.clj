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

(ns sawtooth.ledger.transaction)

(defn- handle-transaction-submit
  "Wraps the previous form in a let which binds the transaction
  id for use in the nested form"
  [send-sym nested-form [id-sym txn-form]]
  (let [txn-sym (gensym 'txn)
        id-sym (if (= id-sym '_) (gensym 'id) id-sym)]
    `(let [~txn-sym ~txn-form
           ~id-sym (cond
                     (and  (list? ~txn-sym) (not (empty? ~txn-sym)))
                     (loop [txns# (map ~send-sym ~txn-sym)
                            ids# ()]
                       (if-let [txn-ch# (first txns#)]
                         (let [id# (cljs.core.async/<! txn-ch#)]
                           (recur (rest txns#)
                                  (conj ids# id#)))
                         (reverse ids#)))

                     (string? ~txn-sym)
                     ~txn-sym

                     :default
                     (cljs.core.async/<! (~send-sym ~txn-sym)))]
       ~(let [res `[~id-sym (if (list? ~txn-sym)
                              (map sawtooth.ledger.transaction/unwrap-vec ~txn-sym)
                              (sawtooth.ledger.transaction/unwrap-vec ~txn-sym))]]
          (if nested-form
           `(if (or (and (map? ~id-sym) (:error? ~id-sym))
                    (and (list? ~id-sym) (reduce #(or %1 (:error? %2)) false ~id-sym)))
              ~res
              ~nested-form)
           res)))))

(defn- chain-transactions*
  [signing-identity txn-family bindings]
  {:pre [(and (vector? bindings) (even? (count bindings)))]}
  (let [send-sym (gensym 'do-send)
        form (->> bindings
                  (partition 2)
                  (reverse)
                  (reduce (partial handle-transaction-submit send-sym) nil))]
    `(cljs.core.async.macros/go
       (let [~send-sym (fn [[txn# annotations#]]
                         (sawtooth.ledger.transaction/send
                           ~signing-identity
                           ~txn-family
                           txn#
                           annotations#))
             ~send-sym (comp ~send-sym sawtooth.ledger.transaction/vectorize)]
         ~form))))

(defmacro chain-transactions
  "Constructs a chain of transactions, binding the resulting transaction ID
  of each submission to a symbol (like a `let`). Returns a channel that will
  have either the transaction ID of the final transaction in the chain, or an
  error if one occurs.

  For example:

  (chain-transactions (wallet/current-signing-identity)
    [first-id (msg/make-transaction {:UpdateType \"/First\"
                                     :name \"UserName\"})
     _ (msg/make-transaction {:UpdateType \"/Second\"
                              :creator first-id
                              :count 10}))"

  [signing-identity txn-family bindings]
  (chain-transactions* signing-identity txn-family bindings))

(defmacro send-chained-transactions
  "Sends a chain of transactions and reports the results"
  [signing-identity txn-family bindings on-done-fn]
  {:pre [(and (vector? bindings) (even? (count bindings)))]}
  `(cljs.core.async.macros/go
     (let [[res# last-txn#]
           (cljs.core.async/<! ~(chain-transactions* signing-identity txn-family bindings))]
       (if-not (:error? res#)
         (sawtooth.ledger.transaction/on-transaction-success last-txn# ~on-done-fn)
         (sawtooth.ledger.transaction/on-transaction-failure last-txn# res#))
       res#)))

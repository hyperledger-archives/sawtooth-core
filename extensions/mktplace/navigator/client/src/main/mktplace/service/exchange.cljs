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
(ns mktplace.service.exchange
  (:require [goog.string :as gstring]
            [sawtooth.math :as math]
            [sawtooth.service.common :as service]))

(def ^:const EXCHANGES_ENDPOINT
  "/api/mktplace/exchanges")
(def ^:const PARTICIPANT_EXCHANGES_ENDPOINT_TEMPLATE
  "/api/mktplace/participants/%s/exchanges")

(defn exchanges
  ([query] (exchanges nil query))
  ([participant query]
   (let [endpoint (if participant
                    (gstring/format PARTICIPANT_EXCHANGES_ENDPOINT_TEMPLATE (:id participant))
                     EXCHANGES_ENDPOINT)]
     (service/fetch-json!
       endpoint
       query
       {:path [:exchanges]
        :on-error {:title "Unable to Load Exchanges"
                   :message "An unknown error occurred
                            while loading Exchanges"}}))))

(defn clear-exchanges []
  (service/clear-path! [:exchanges] {:data [] :count 0}))

(defn compute-model-holdings
  "Computes the predicted holding values based on the given set of offers
  with the input quantity"
  [offers selected-initial-holding final-holding initial-quantity]
  (letfn [(model-change [holding delta]
            (when holding
              (if (get-in holding [:asset-settings :consumable] true)
                (update-in holding [:count] (partial + delta))
                holding)))]
    (if-not (empty? offers)
      (loop [initial-holding selected-initial-holding
             offers offers
             quantity initial-quantity
             pairs []]
        (let [offer (first offers)

              ratio  (get offer :ratio)

              input-delta  (if initial-holding
                             (- quantity))
              output-delta (if final-holding
                             (math/floor (* quantity ratio)) 0)

              left-input (model-change initial-holding input-delta)
              right-input (model-change (get offer :input) (- input-delta))]
          (if (< 1 (count offers))
            (let [remaining-offers (rest offers)
                  next-ratio (get (first remaining-offers) :ratio 1) ]
            (recur
              (get offer :output)
              (rest offers)
              output-delta
              (conj pairs
                    {:left left-input
                     :right right-input})))
            (conj pairs
                  {:left left-input
                   :right right-input}
                  {:left (model-change (get offer :output) (- output-delta))
                   :right (model-change final-holding output-delta)}))))
      [{:left (model-change selected-initial-holding (- initial-quantity))
        :right (model-change final-holding initial-quantity)}])))

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
(ns mktplace.service.offer
  (:require [cljs.core.async :as async :refer [take! put!]]
            [taoensso.timbre :as timbre
             :refer-macros [debugf warnf]]
            [goog.string :as gstring]
            [sawtooth.utils :refer [index-of]]
            [sawtooth.state :refer [state-change-ch app-state]]
            [sawtooth.service.common :as service]
            [mktplace.transactions :as txns]))


(def ^:const PAGE_SIZE 100)

(def ^:const ACTIONABLE_OFFERS_ENDPOINT_TEMPLATE
  "/api/mktplace/participants/%s/actionable_offers")

(def ^:const OWNED_OFFERS_ENDPOINT_TEMPLATE
  "/api/mktplace/participants/%s/offers")

(defn- fetch-offers
  [endpoint-template participant-id query]
  (service/fetch-json!
    (gstring/format endpoint-template participant-id)
    query
    {:path [:offers]
     :on-error {:title "Unable to Load Offers"
                :message "An unknown error occured
                         while loading offers."}}))

(defn owned-offers
  [{participant-id :id} query]
  (fetch-offers OWNED_OFFERS_ENDPOINT_TEMPLATE participant-id query))

(defn available-offers
  [{participant-id :id} query]
  (fetch-offers ACTIONABLE_OFFERS_ENDPOINT_TEMPLATE participant-id query))

(defn submit-offer [wallet-id  participant sell-offer]
  (mktplace.transactions/register-sell-offer wallet-id participant sell-offer))

(defn- update-offer [offer f & args]
  (when-let [i (index-of #(= (:id offer) (:id %)) (get-in @app-state [:offers :data]))]
    (put! state-change-ch {:path [:offers :data i]
                           :value (apply f offer args)})))

(defn revoke [wallet-id participant offer]
  (mktplace.transactions/unregister-sell-offer wallet-id participant offer)
  (update-offer offer assoc :revoked true))

(defn exchange-offers-with
  "Given a participant and a query (of any one of nput, output, limit and page)
  it will place the results on the app state at [:exchange :insert :offers]"
  [{participant-id :id} {:keys [input output limit page]}]
  (let [query (cond-> {:participantId (str "!" participant-id)
                       :page 0}
                input (assoc :inputAssetId input)
                output (assoc :outputAssetId output)
                page (assoc :page page)
                limit (assoc :limit limit))]
    (service/fetch-json!
      (gstring/format ACTIONABLE_OFFERS_ENDPOINT_TEMPLATE participant-id)
      query
      {:path [:exchange :insert :offers]
       :on-error {:title "Unable to Load Offers"
                  :message "An unknown error occured
                           while loading offers"}})))

(defn clear-exchange-offers-with
  "Clears the results of exchange-offers-with from the app state."
  []
  (service/clear-path! [:exchange :insert]))

(defn exchange-offer
  "Loads the offer with the given id into the app-state in a vector at
  [:exchange :offers]."
  [{participant-id :id} offer-id]
  (service/fetch-json!
    (gstring/format (str OWNED_OFFERS_ENDPOINT_TEMPLATE "/" offer-id) participant-id)
    {:xform (fn [offer]
              {:path [:exchange :offers]
               :action #(conj % offer)})
     :on-error {:title "Unable to Load Offer"
                :message "An unknown error occured
                         while loading the selected offer"}}))

(defn insert-exchange-offer
  "Inserts the given offer into the vector of offers in the app-state at
  [:exchange :offers].  If flag before is truthy, the offer is inserted at
  the beginning of the vector"
  [offer before?]
  (let [action-fn (if before?
                    #(vec (concat [offer] %))
                    #(conj (vec %) offer))]
    (put! state-change-ch
          {:path [:exchange :offers]
           :action action-fn })))

(defn release-exchange-offer
  "Removes the offer with the given id from the vector of offers in the
  app-state at [:exchange :offers]."
  [offer-id]
  (put! state-change-ch {:path [:exchange :offers]
                         :action (fn [offers] (remove #(= offer-id (:id %)) offers))}))

(defn clear-exchange-offers
  "Removes the app-state of an on-going exchange"
  []
  (service/clear-path! [:exchange]))

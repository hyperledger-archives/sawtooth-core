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

(ns bond.routes
  (:require [cljs.core.async :as async :refer [put!]]
            [sawtooth.state :refer [state-change-ch]]
            [secretary.core :as secretary :refer-macros [defroute]]))

(defn- change-route
  ([route-key] (change-route route-key {}))
  ([route-key args]
   (put! state-change-ch {:path [:route]
                          :value [route-key args]})))

(defroute home-path "/" []
  (change-route :home))

(defroute welcome "/welcome" []
  (change-route :welcome))

(defroute new-wif "/new-wif" []
  (change-route :new-wif))

(defroute add-wif "/add-wif" []
  (change-route :add-wif))

(defroute quote-form "/quote-form" []
  (change-route :quote-form))

(defroute order-form "/order-form/:bond-id" [bond-id query-params]
  (change-route :order-form (assoc query-params :bond-id bond-id)))

(defroute quote-list "/quotes/:bond-id" [bond-id]
  (change-route :quote-list {:bond-id bond-id}))

(defroute order-list "/order-list" []
  (change-route :order-list))

(defroute bond-list "/bond-list" []
  (change-route :bond-list))

(defroute bond-detail "/bonds/:bond-id" [bond-id]
  (change-route :bond-detail {:bond-id bond-id}))

(defroute bond-form "/bond-form" []
  (change-route :bond-form))

(defroute participant-form "/participant-form" []
  (change-route :participant-form))

(defroute participant-update "/participant-update" []
  (change-route :participant-update))

(defroute org-form "/org-form" []
  (change-route :org-form))

(defroute portfolio "/portfolio" []
  (change-route :portfolio-holdings))

(defroute portfolio-holdings "/portfolio/holdings" []
  (change-route :portfolio-holdings))

(defroute portfolio-receipts "/portfolio/receipts" []
  (change-route :portfolio-receipts))

(defroute portfolio-settlements "/portfolio/settlements" []
  (change-route :portfolio-settlements))

(defroute transaction-history "/transactions" []
  (change-route :transaction-history))

(defroute "*" []
  (change-route :not-found))

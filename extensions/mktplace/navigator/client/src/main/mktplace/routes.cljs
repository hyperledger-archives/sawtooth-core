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
(ns mktplace.routes
  (:require [cljs.core.async :as async :refer [put!]]
            [sawtooth.state :refer [state-change-ch]]
            [secretary.core :as secretary :refer-macros [defroute]]))

; Sometimes needed to force a reload of the routes
#_(secretary/reset-routes!)

(defn- change-route
  ([route-key] (change-route route-key {}))
  ([route-key args]
   (put! state-change-ch {:path [:route]
                          :value [route-key args]})))

(defroute home-path "/" []
  (change-route :home))

(defroute dashboard-path "/:participant-id/dashboard" [participant-id]
  (change-route :home {:participant-id participant-id}))

(defroute exchanges-path "/:participant-id/exchanges" [participant-id]
  (change-route :exchanges {:participant-id participant-id}))

(defroute asset-create-path "/assets/create" []
  (change-route :asset-form))

(defroute holding-create-path "/holdings/create" []
  (change-route :holding-form))

(defroute offers-path "/:participant-id/offers" [participant-id]
  (change-route :offers {:participant-id participant-id}))

(defroute sell-offer-path "/offers/create" []
  (change-route :sell-offer-form))

(defroute exchange-offer-path "/exchange/:initial-offer-id" [initial-offer-id]
  (change-route :exchange {:initial-offer-id initial-offer-id}))

(defroute transfer-path "/transfer" []
  (change-route :transfer))

(defroute portfolio-path "/:participant-id/portfolio" [participant-id]
  (change-route :portfolio {:participant-id participant-id}))

(defroute intro-path "/intro" []
  (change-route :intro))

(defroute new-wif-path "/create-key" []
  (change-route :new-wif))

(defroute add-wif-path "/upload-key" []
  (change-route :add-wif))

(defroute create-participant-path "/create-participant/:address" [address]
  (change-route :create-participant {:address address}))

; Block-chain routes
(defroute block-transactions-path "/transactions" []
  (change-route :block-transactions))

(defroute "*" []
  (change-route :not-found))

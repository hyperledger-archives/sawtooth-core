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
(ns mktplace.components.dashboard
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [mktplace.routes :as routes]
            [mktplace.service.offer :as offer]
            [mktplace.service.exchange :as exchange]
            [sawtooth.components.core
             :refer-macros [when-changed]]
            [mktplace.components.offers :refer [offer-table]]
            [mktplace.components.exchanges :refer [exchange-table]]))


(defn- make-query [app-state]
  (let [selected-asset-id (get-in app-state [:selections :asset :id])
        selected-holding-id (get-in app-state [:selections :holding :id])]
    {:limit 5
     :assetId selected-asset-id
     :holdingId selected-holding-id}))

(defn- load-offers! [app-state]
  (when-let [participant (or (:view-participant app-state)
                             (:participant app-state))]
    (let [query (make-query app-state)]
      (offer/available-offers participant query))))

(defn- load-exchanges! [app-state]
  (exchange/exchanges (make-query app-state)))

(defn dashboard [data owner]
  (reify
    om/IDisplayName
    (display-name [_] "Dashboard")

    om/IInitState
    (init-state [_] {})

    om/IWillMount
    (will-mount [_]
      (load-offers! data)
      (load-exchanges! data))

    om/IWillReceiveProps
    (will-receive-props [_ next-state]
      (when-changed owner next-state [:block :selections :view-participant]
        (load-offers! next-state))

      (when-changed owner next-state [:block :selections]
        (load-exchanges! next-state)))

    om/IRenderState
    (render-state [_ state]
      (let [participant-id (or (get-in data [:view-participant :id])
                               (get-in data [:participant :id]))
            link-args {:participant-id participant-id}
            assets (get data :assets)
            participants (get data :participants)
            offers (get-in data [:offers :data])
            exchanges (get-in data [:exchanges :data])]
        (html [:div.container-fluid
               [:div.row
                (om/build offer-table
                          {:offers offers
                           :participants participants
                           :assets assets
                           :title [:a {:href (routes/offers-path link-args)}
                                   "Latest Open Offers"]})]
               [:div.row
                (om/build exchange-table
                          {:exchanges exchanges
                           :participants participants
                           :assets assets
                           :title [:a {:href (routes/exchanges-path link-args)}
                                   "Latest Exchanges"]})]])))))

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

(ns bond.components.portfolio
  (:require [om.core :as om]
            [sablono.core :refer-macros [html]]
            [sawtooth.router :as router]
            [bond.routes :as routes]
            [bond.components.core :as core]
            [bond.components.holding-list
             :refer [holdings-list]]
            [bond.components.receipt-list
             :refer [receipts-list]]
            [bond.components.settlement-list
             :refer [settlements-list]]))

(defn participant-firm-name [data]
  (->> (core/participant-firm data)
       :name))

(defn- portfolio-nav
  [label href route-key current-route]
  [:a.list-group-item
   {:href href
    :class (if (= current-route route-key) "active")}
   label])

(defn portfolio [data owner]
  (let [current-route (get-in data [:route 0])]
  (om/component
    (html
      [:div.container
       [:h3 "Portfolio for " (participant-firm-name data)]

       [:div.row
        [:div.col-md-4
         [:div.list-group
          (portfolio-nav "Holdings" (routes/portfolio-holdings) current-route :portfolio-holdings)
          (portfolio-nav "Receipts" (routes/portfolio-receipts) current-route :portfolio-receipts)
          (portfolio-nav "Settlements" (routes/portfolio-settlements) current-route :portfolio-settlements)]]
        [:div.col-md-8
         (router/route-handler data owner)]]]))))

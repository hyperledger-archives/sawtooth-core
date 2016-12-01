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

(ns bond.components.settlement-list
  (:require [om.core :as om]
            [sablono.core :refer-macros [html]]
            [cljs.pprint :refer [cl-format]]
            [bond.components.page-container :refer [page-container]]
            [bond.components.core
             :refer [table bond->name format-timestamp format-currency]]
            [bond.service.history :refer [load-settlements! clear-settlements!]]))

(defn- settlement-row
  [{:keys [action bond-quantity currency-amount quoting-firm ordering-firm] :as settlement}]
  [(bond->name (get-in settlement [:quote-bond-holding :asset]))
   action
   (cl-format nil "~:d" bond-quantity)
   (format-currency currency-amount (if (= action "Sell")
                                      (get-in settlement [:order-currency-holding :asset-id])
                                      (get-in settlement [:quote-currency-holding :asset-id])))
   quoting-firm
   ordering-firm])

(defn- settlements-table [data owner]
  (om/component
    (let [settlements (:rows data)]
      (html
        [:div.settlements-table
         (table
           ["Bond"
            "Action"
            "Quantity"
            "Amount"
            "Quoting Firm"
            "Ordering Firm"]
           (map settlement-row settlements)
           "No settlements found.")]))))

(defn settlements-list [data owner]
  (om/component
    (om/build page-container data
              {:opts {:load-fn (fn [page limit]
                                 (load-settlements! (get-in data [:participant :firm-id])
                                                    {:page page :limit limit}))
                      :unload-fn clear-settlements!
                      :base-path :settlements
                      :table-component settlements-table}})))

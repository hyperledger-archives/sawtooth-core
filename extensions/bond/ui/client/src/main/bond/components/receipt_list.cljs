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

(ns bond.components.receipt-list
  (:require [om.core :as om]
            [sablono.core :refer-macros [html]]
            [cljs.pprint :refer [cl-format]]
            [bond.components.page-container :refer [page-container]]
            [bond.components.core
             :refer [table heading bond->name format-timestamp format-currency]]
            [bond.service.history :refer [load-receipts! clear-receipts!]]))

(defn- payer [orgs {:keys [issuer]}]
  (->> orgs
       (filter #(or (= (:ticker %) issuer) (= (:pricing-source %) issuer)))
       first
       :name))

(defn- receipt-row-fn [orgs]
  (fn [{:keys [timestamp bond payment-type payee amount coupon-date]}]
    [(format-timestamp timestamp)
     payment-type
     (bond->name bond)
     (payer orgs bond)
     (format-currency amount)
     (if coupon-date
       [:span [:i "Coupon Date: "] coupon-date]
       "")]))

(defn- receipts-table [data owner]
  (om/component
    (let [receipts (:rows data)
          organizations (:organizations data)]
      (html
        [:div.receipts-table
         (table
           ["Date"
            "Type"
            "Bond"
            "Payer"
            "Amount"
            "Additional"]
           (map (receipt-row-fn organizations) receipts)
           "No receipts found.")]))))

(defn receipts-list [data owner]
  (om/component
    (om/build page-container data
              {:opts {:load-fn (fn [page limit]
                                 (load-receipts! (get-in data [:participant :firm-id])
                                                 {:page page :limit limit}))
                      :unload-fn clear-receipts!
                      :base-path :receipts
                      :additional-keys {:organizations [:organizations]}
                      :table-component receipts-table}})))

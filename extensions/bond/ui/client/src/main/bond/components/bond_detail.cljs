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

(ns bond.components.bond-detail
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.components.core
             :refer-macros [when-new-block]]
            [bond.components.core
             :refer [description]]
            [bond.service.bond :as bond-svc]
            [bond.routes :as routes]))


(defn bond-id [app-state]
  (get-in app-state [:route 1 :bond-id]))

(defn bond-detail [data owner]
  (reify

    om/IWillMount
    (will-mount [_]
      (let [isin-or-cusip (bond-id data)]
        (bond-svc/load-bond! isin-or-cusip)))

    om/IWillReceiveProps
    (will-receive-props [_ next-state]
      (when-new-block owner next-state
        (let [isin-or-cusip (bond-id next-state)]
          (bond-svc/load-bond! isin-or-cusip))))

    om/IWillUnmount
    (will-unmount [_]
      (bond-svc/clear-bond!))


    om/IRender
    (render [_]
      (let [bond (get data :bond)]
      (html
        [:div.container
         [:h2 "Bond Details"]
         (if bond
           [:div
            [:div.row
             [:h4 "Issuer"]
             (description
               {"Name" (get-in bond [:issuing-firm :name])
                "Industry" (get-in bond [:issuing-firm :industry] "None Specified")
                "Ticker" (get-in bond [:issuing-firm :ticker])})]

            [:div.row
             [:h4 "Corporate Debt Ratings"]
             (description
                (get bond :corporate-debt-ratings))]

            [:div.row
             [:h4 "Identifiers"]
             (description
                {"CUSIP" (get bond :cusip)
                 "ISIN" (get bond :isin)})]

            [:div.row
             [:h4 "Bond Details"]
             (description
                {"1st Settle Date" (get bond :first-settlement-date "None")
                 "Maturity Date" (get bond :maturity-date)
                 "Amount Outstanding" (get bond :amount-outstanding)})]

            [:div.row
             [:h4 "Coupon Details"]
             (description
               (cond-> {"Type" (get bond :coupon-type)
                        "Rate" (get bond :coupon-rate)
                        "1st Date" (get bond :first-coupon-date)
                        "Frequency" (get bond :coupon-frequency)}
                  (get bond :coupon-benchmark) (assoc "Benchmark" (get bond :coupon-benchmark))))]

            [:div.row
             [:a.btn.btn-default {:href (routes/bond-list)} "Back to Bonds"]]])])))))

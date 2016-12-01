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

(ns bond.components.quote-list
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.state :refer [app-state]]
            [sawtooth.components.core
             :refer [->num]]
            [bond.routes :as routes]
            [bond.service.quote :refer [quotes! clear-quotes!]]
            [bond.components.page-container :refer [page-container]]
            [bond.components.core :as core :refer [bid-ask-pair print-yield]]))

(defn- qty->size [qty]
  (/ qty 1000))

(defn- quote-row [q bond]
  [(:firm q)
   (:firm-name q)
   (bid-ask-pair q "price" "/")
   (bid-ask-pair q "price" "/" #(print-yield % bond))
   (bid-ask-pair q "qty" "x" qty->size)
   (str (if (:pending q) "~" "")
        (core/format-timestamp (:timestamp q) :hour-minute))])

(def ^:const PAGE_SIZE 10)

(defn- quote-table [data owner]
  (om/component
    (let [quotes (:rows data)
          bond (:bond data)
          bond-id (:bond-id data)]
      (html
        (core/table
          ["PSC"
           "Firm Name"
           "Bid / Ask Prices"
           "Bid / Ask Yields"
           "Bid / Ask Sizes (M)"
           "Time of Quote"]
          (map #(quote-row % bond) quotes)
          (str "No Quotes found for " bond-id))))))

(defn quote-list [data owner]
  (reify
    om/IRender
    (render [_]
      (let [participant-id (get-in data [:participant :id])
            bond-id (get-in data [:route 1 :bond-id])
            bond (get-in data [:quotes-info :bond])
            best (core/best-quote bond)]
        (html
          [:div.container
           (core/heading "View Quotes")

           (when bond
             [:div.row.quote-bond-details
              [:div.col-sm-4 (core/bond->name bond)]
              [:div.col-sm-2 (if best
                               (bid-ask-pair best "price" "/")
                               "N/A")]
              [:div.col-sm-2 (if best
                               (bid-ask-pair best "price" "/" #(print-yield % bond))
                               "N/A")]
              [:div.col-sm-2 (core/link-button
                               (routes/order-form
                                 {:query-params {:action "Buy"}
                                  :bond-id bond-id})
                               "Buy"
                               {:class "btn-order"
                                :disabled (nil? best)})]
              [:div.col-sm-2 (core/link-button
                               (routes/order-form
                                 {:query-params {:action "Sell"}
                                  :bond-id bond-id})
                               "Sell"
                               {:class "btn-order"
                                :disabled (nil? best)})]])

           (om/build page-container data
                     {:opts {:load-fn (fn [page limit]
                                        (when-let [bond-id (get-in data [:route 1 :bond-id])]
                                          (quotes! participant-id bond-id
                                                   {:page page :limit limit})))
                             :unload-fn clear-quotes!
                             :base-path [:quotes-info :quotes]
                             :additional-keys {:bond [:quotes-info :bond]
                                               :bond-id [:route 1 :bond-id]}
                             :table-component quote-table}})])))))

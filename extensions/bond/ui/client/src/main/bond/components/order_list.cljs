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

(ns bond.components.order-list
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [taoensso.timbre :refer-macros [spy]]
            [sawtooth.state :refer [app-state]]
            [sawtooth.utils :as utils]
            [sawtooth.ledger.keys :refer [get-key-pair]]
            [sawtooth.router :as router]
            [bond.routes :as routes]
            [bond.components.core :refer [format-timestamp] :as core]
            [bond.service.order :refer [orders! clear-orders!]]
            [bond.transactions :refer [create-settlement]]
            [sawtooth.components.core
             :refer [paging]
             :refer-macros [when-new-block handle-event]]))

(def ^:const PAGE_SIZE 10)

(defn- fetch-orders [participant-id owner]
  (orders! participant-id
           {:page (om/get-state owner :page)
            :creator-only (om/get-state owner :creator-only)
            :limit PAGE_SIZE
            :check-pending true}))

(defn- settle [id owner]
  (create-settlement (get-key-pair) id
                     #(fetch-orders (-> (om/get-props owner) (get-in [:participant :id])) owner)))

(defn- settle-btn [{:keys [id pending]} owner]
  [:a.btn.btn-sm.btn-primary.btn-settle
   {:disabled pending
    :on-click #(settle id owner)}
   "Settle"])

(defn- order-row [order participant owner]
  [(if (:pending order)
     "Pending"
     (format-timestamp (:timestamp order 0)))
   (:trader order "Unknown")
   (:id (core/bond-id order))
   (core/bond->name (:bond order))
   (:status order)
   (:order-type order)
   (:quantity order)
   (when (and (= "Matched" (:status order))
              (= (:firm-id order) (:firm-id participant)))
     (settle-btn order owner))])

(defn order-list [data owner]
  (letfn [(do-load [] (fetch-orders (get-in data [:participant :id]) owner))
          (go-to-page [page]
            (om/set-state! owner :page page)
            (do-load))]
    (reify
      om/IInitState
      (init-state [_] {:page 0})

      om/IWillMount
      (will-mount [_]
        (do-load))

      om/IWillReceiveProps
      (will-receive-props [_ next-state]
        (when-new-block owner next-state
          (do-load)))

      om/IWillUnmount
      (will-unmount [_]
        (clear-orders!))

      om/IRenderState
      (render-state [_ state]
        (let [participant (get data :participant)
              orders (get-in data [:orders :data])
              total (get-in data [:orders :count])]
          (html

            [:div.container
             (core/heading "View Orders")
             [:div.view-options
              [:div.radio-inline
               [:label
                [:input {:type "radio"
                         :on-change (handle-event
                                      (om/set-state! owner :creator-only nil)
                                      (do-load))
                         :checked (nil? (:creator-only state))}]
                "All Orders"]]
              [:div.radio-inline
               [:label
                [:input {:type "radio"
                         :on-change (handle-event
                                      (om/set-state! owner :creator-only true)
                                      (do-load))
                         :checked (:creator-only state)}]
                "Only My Orders"]]]

             (core/table
               ["Order Time"
                "Trader"
                "ISIN/CUSIP"
                "Bond"
                "Order Status"
                "Type"
                "Quantity"
                nil]
               (map #(order-row % participant owner) orders)
               "No Orders Found")

         (if (< PAGE_SIZE total)
           [:div.row
            (om/build paging {:current-page (om/get-state owner :page)
                              :total-items total
                              :items-per-page PAGE_SIZE
                              :go-to-page-fn go-to-page})])]))))))

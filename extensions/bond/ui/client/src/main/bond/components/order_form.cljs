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

(ns bond.components.order-form
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [taoensso.timbre :as log :include-macros]
            [sawtooth.state :refer [app-state]]
            [sawtooth.ledger.keys :refer [get-key-pair address]]
            [sawtooth.components.core :as saw :include-macros]
            [sawtooth.router :as router]
            [bond.routes :as routes]
            [bond.transactions :refer [create-order]]
            [bond.service.bond :refer [load-bond! clear-bond!]]
            [bond.service.participant :refer [participant!]]
            [bond.components.core :as core
             :refer [form-section description description-entry]]))

(defn- set-initial-state [data]
  (let [initial-state (-> (:order-form (apply hash-map (:route data)))
                          (assoc :order-type "Market"))]
    (if (:action initial-state) initial-state
      (assoc initial-state :action "Buy"))))

(defn- is-valid? [{:keys [quantity price order-type]}]
  (and quantity (or (= "Market" order-type)
                    (and price (re-find core/price-pattern price)))))

(defn- set-best!
  ([owner bond] (set-best! owner (om/get-state owner) bond))
  ([owner state bond]
   (when bond
     (let [{:keys [bid-price ask-price]} (core/best-quote bond)
                   set-best-fields!
                   #(do (om/set-state! owner :best-price %)
                        (om/set-state! owner :best-yield
                                       (core/print-yield % bond)))]
             (if (= "Sell" (:action state))
               (set-best-fields! bid-price)
               (set-best-fields! ask-price))))))

(defn- submit-order [participant-id state bond-ids firm-id owner]
  (if (is-valid? state)
    (do (log/debugf "state: %s" state)
        (om/set-state! owner :submitted true)
        (create-order
          (get-key-pair)
          participant-id
          (merge state bond-ids {:firm-id firm-id})
          #(router/push (routes/order-list))))
    (core/invalid-tip! "Create Order" "Form is invalid. Do you have a Price/Yield?")))

(defn- radio-buttons [owner k buttons label]
  [:div [:label label]
   (saw/radio-buttons owner k
                      (map #(vector % %) buttons)
                      {:inline? true
                       :required true})])

(defn order-form [data owner]
  (let [bond-id (get-in data [:route 1 :bond-id])
        participant-id (get-in data [:participant :id])
        initial-state (set-initial-state data)
        owner-state! (partial om/set-state! owner)
        owner-field (partial saw/text-field owner)]
    (reify
      om/IInitState
      (init-state [_] initial-state)

      om/IWillMount
      (will-mount [_]
        (load-bond! bond-id))

      om/IWillReceiveProps
      (will-receive-props [_ next-props]
        (saw/when-new-block owner next-props
          (load-bond! bond-id))
        (when (not= (:bond next-props) (:bond data))
          (set-best! owner (:bond next-props))))

      om/IWillUnmount
      (will-unmount [_]
        (clear-bond!))

      om/IWillUpdate
      (will-update [_ _ next-state]
        (set-best! owner next-state (:bond data)))

      om/IRenderState
      (render-state [_ {:keys [price] :as state}]
        (html
          [:div.container
           (core/heading "Buy/Sell Order")
           (if-let [bond (:bond data)]
             (letfn [(print-price [yield]
                       (-> (core/yield->price yield (:coupon-rate bond))
                           (core/format-price)))]
             [:form.form.quote-form
              {:ref "order-form"
               :on-submit
               (saw/handle-submit
                 owner "order-form"
                 (submit-order
                   participant-id
                   (select-keys state [:action :price :quantity :order-type])
                   (select-keys bond [:isin :cusip])
                   (get-in data [:participant :firm-id])
                   owner))}

              (form-section
                "Bond Details" "details"
                (core/divided-rows
                  (description [(description-entry
                                  (:label (core/bond-id bond))
                                  bond
                                  (:key (core/bond-id bond)))
                                (description-entry "Coupon Rate" bond :coupon-rate)])
                  (description [(description-entry "Issuer" bond :issuer)
                                (description-entry "Maturity Date" bond :maturity-date)])))

              (let [best-quote (core/best-quote bond)]
                (form-section
                  "Best Quote" "best"
                  (core/divided-rows
                    (description [(description-entry "Bid Time" best-quote :bid-time
                                                     #(core/format-timestamp %))])
                    (description [(description-entry "Ask Time" best-quote :ask-time
                                                     #(core/format-timestamp %))])
                    (description [(description-entry "Bid Price" best-quote :bid-price)
                                  (description-entry "Bid Quantity" best-quote :bid-qty)])
                    (description [(description-entry "Ask Price" best-quote :ask-price)
                                  (description-entry "Ask Quantity" best-quote :ask-qty)]))))

                (let [market? (= "Market" (:order-type state))]
                  (form-section
                    "Order" "order"
                    (core/boot-row
                      (radio-buttons owner :action ["Buy" "Sell"] "Action")
                      (radio-buttons owner :order-type ["Market" "Limit"] "Type"))
                    (core/boot-row
                      (owner-field :quantity "Quantity"
                                   {:required true
                                    :type "number"
                                    :min 0
                                    :parse-fn saw/->int})
                      (owner-field
                        (if market? :best-price :price)
                        (if market? "Best Price" "Limit Price")
                        {:disabled market?
                         :pattern core/price-pattern
                         :did-change-fn #(owner-state!
                                           :yield (if-not (empty? %2)
                                                    (core/print-yield %2 bond)))})
                      (owner-field
                        (if market? :best-yield :yield)
                        (if market? "Best Yield" "Limit Yield")
                        {:disabled market?
                         :did-change-fn
                         #(owner-state! :price (if-let [yield (saw/->float %2)]
                                                 (print-price yield)
                                                 ""))}))))

              (saw/form-buttons owner initial-state
                                {:submit {:label "Create Order"
                                          :disabled (:submitted state)}})])
             [:p "Loading..."])])))))

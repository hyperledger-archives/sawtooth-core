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

(ns bond.components.quote-form
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [goog.string :as gstring]
            [sawtooth.state :refer [app-state]]
            [sawtooth.ledger.keys :refer [get-key-pair]]
            [sawtooth.components.core :as saw-core :include-macros]
            [sawtooth.router :as router]
            [bond.routes :as routes]
            [bond.transactions :refer [create-quote]]
            [bond.service.organization :refer [organizations!]]
            [bond.service.quote :refer [latest-quote! clear-latest-quote!]]
            [bond.service.bond
             :refer [load-bond! clear-bond!
                     load-bond-identifiers! clear-bond-identifiers!]]
            [bond.components.core :as core
             :refer [description description-entry]]))

(defn- is-valid? [state]
  (and (reduce #(and %1 (%2 state))
               true [:bid-qty :ask-qty])
       (reduce #(and %1 (not (empty? (%2 state))))
               true [:firm :bond-id])
       (reduce #(and %1 (%2 state) (re-find core/price-pattern (%2 state)))
               true [:bid-price :ask-price])))

(defn- send-quote [participant-id {:keys [bond-id] :as state} owner]
  (if (is-valid? state)
      (let [full-state (merge state (if (re-matches core/isin-pattern bond-id)
                                    {:isin bond-id}
                                    {:cusip bond-id}))]
        (om/set-state! owner :submitted true)
        (create-quote
          (get-key-pair)
          participant-id
          full-state
          #(router/push (routes/quote-list {:bond-id (:bond-id state)}))))
      (core/invalid-tip! "Issue")))

(defn- load-info! [bond-id pricing-source]
  (load-bond! bond-id)
  (latest-quote! bond-id pricing-source))

(defn- clear-info! []
  (clear-bond!)
  (clear-latest-quote!))

(defn update-remote-data [owner bond-id pricing-source]
  (when (not= (om/get-render-state owner :bond-id) bond-id)
    (if-not (empty? bond-id)
      (load-info! bond-id pricing-source)
      (clear-info!))))

(defn quote-form [data owner]
  (let [firm (core/participant-firm data)
        initial-state {:firm (:pricing-source firm)}

        owner-field (partial saw-core/text-field owner)
        num-field #(owner-field %1 %2
                                {:type "number"
                                 :min 0
                                 :parse-fn saw-core/->int
                                 :required true})]
    (reify
      om/IInitState
      (init-state [_] initial-state)

      om/IWillMount
      (will-mount [_]
        (load-bond-identifiers!))

      om/IWillReceiveProps
      (will-receive-props [_ new-props]
        (let [pricing-source (:pricing-source (core/participant-firm new-props))]
          (when-not (om/get-state owner :firm)
            (om/set-state! owner :firm pricing-source))

          (saw-core/when-new-block owner new-props
            (load-bond-identifiers!)
            (when-let [id (om/get-state owner :bond-id)]
              (load-bond! id)
              (latest-quote! id pricing-source)))))

      om/IWillUpdate
      (will-update [_ _ {:keys [bond-id firm]}]
        (update-remote-data owner bond-id firm))

      om/IWillUnmount
      (will-unmount [_]
        (clear-bond!)
        (clear-bond-identifiers!)
        (clear-latest-quote!))

      om/IRenderState
      (render-state [_ state]
        (let [{bond :bond prior-quote :latest-quote} data
              participant-id (get-in data [:participant :id])
              firm (core/participant-firm data)]
        (html
          [:div.container
           (core/heading "Issue Quote")
           [:form.form.quote-form
            {:ref "quote-form"
             :on-submit (saw-core/handle-submit owner "quote-form"
                          (send-quote participant-id state owner))}

            (core/form-section "Firm" "firm"
                               (saw-core/static-field
                                 "Pricing Source"
                                 (gstring/format
                                   "%s (%s)"
                                   (:pricing-source firm)
                                   (:name firm)))
                               #_(saw-core/select-field owner :firm "Pricing Source"
                                                      (source-options data)
                                                      {:required true}))

            (core/form-section "Bond Details" "bond"
                               (saw-core/select-field owner :bond-id "CUSIP/ISIN"
                                                      (->> (:bond-identifiers data)
                                                           (map #(assoc (core/bond-id %) :name (:name %)))
                                                           (map (fn [{:keys [id name]}]
                                                                  [:option {:key id :value id}
                                                                           (str id " - " name)]))
                                                           (conj [[:option {:key 0} "Select a bond..."]]))
                                                      {:required true})
                               (core/divided-rows
                                 (description [(description-entry "Issuer" bond :issuer)])
                                 (description [(description-entry "Maturity Date" bond :maturity-date)])))

            (core/form-section "Prior Quote" "prior"
                               (description [(description-entry "Quote Time" prior-quote :timestamp
                                                                #(core/format-timestamp % :date-hour-minute))])
                               (core/divided-rows
                                 (description [(description-entry "Bid Price" prior-quote :bid-price)
                                               (description-entry "Bid Quantity" prior-quote :bid-qty)])
                                 (description [(description-entry "Ask Price" prior-quote :ask-price)
                                               (description-entry "Ask Quantity" prior-quote :ask-qty)])))

            (core/form-section "Quote Details" "details"
                               (core/divided-rows
                               (owner-field :bid-price
                                            (core/header-note
                                              "Bid Price"
                                              "what's this?"
                                              "http://www.investopedia.com/terms/b/bondquote.asp")
                                            {:required true :pattern core/price-pattern})
                               (owner-field :ask-price
                                            (core/header-note
                                              "Ask Price"
                                              "what's this?"
                                              "http://www.investopedia.com/terms/b/bondquote.asp")
                                            {:required true :pattern core/price-pattern})
                               (num-field :bid-qty "Bid Quantity")
                               (num-field :ask-qty "Ask Quantity")))

            (saw-core/form-buttons owner initial-state
                                   {:submit {:label "Issue"
                                             :disabled (:submitted state)}
                                    :reset {:form-ref "quote-form"}})]]))))))

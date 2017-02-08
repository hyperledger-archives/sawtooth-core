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

(ns bond.components.org-form
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.state :refer [app-state]]
            [sawtooth.ledger.keys :refer [address get-key-pair]]
            [sawtooth.components.core :as saw :include-macros]
            [sawtooth.router :as router]
            [bond.routes :as routes]
            [bond.transactions :refer [create-issuing-org create-trading-org]]
            [bond.service.participant :refer [participant!]]
            [bond.service.bond :as bond]
            [bond.components.core :as core]))

(def src-pattern #"^[A-Z]{4}$")

(defn- is-valid? [{:keys [name ticker pricing-source]}]
  (and (not (empty? name))
       (or (not (empty? ticker))
           (and pricing-source (re-find src-pattern pricing-source)))))

(defn- create-org [state bond-ids participant-id owner]
  (if (is-valid? state)
    (let [on-done-fn #(router/push (routes/home-path))]
      (om/set-state! owner :submitted true)
      (if (:pricing-source state)
        (create-trading-org (get-key-pair)
                            (assoc state :authorization
                              [{:ParticipantId participant-id
                                :Role "marketmaker"}])
                            bond-ids
                            on-done-fn)
        (create-issuing-org (get-key-pair)
                            state
                            on-done-fn)))
    (core/invalid-tip! "Create" "Form invalid. You need a Ticker or a Pricing Source.")))

(defn org-form [data owner]
  (let [participant-id (get-in data [:participant :id])
        owner-field (partial saw/text-field owner)]
    (reify
      om/IWillMount
      (will-mount [_]
        (participant! (address (get-key-pair)))
        (bond/load-bond-identifiers!))

      om/IWillUnmount
      (will-unmount [_]
        (bond/clear-bond-identifiers!))

      om/IRenderState
      (render-state [_ state]
        (html
          [:div.container
           (core/heading "Create Organization")
           [:form.form.org-form
            {:ref "create-org"
             :on-submit (saw/handle-submit owner "create-org"
                                           (create-org state
                                                       (:bond-identifiers data)
                                                       participant-id
                                                       owner))}

            (core/form-section "Organization Info" "org-info"
                               (core/divided-rows
                                 (owner-field :name "Name" {:required true})
                                 (owner-field :industry (core/header-note "Industry" "optional"))
                                 (owner-field :ticker "Ticker" {:disabled (:pricing-source state)})
                                 (owner-field :pricing-source
                                              (core/header-note "Pricing Source" "e.g. BGDR")
                                              {:disabled (:ticker state) :pattern src-pattern})))

            (saw/form-buttons owner {}
                              {:submit {:label "Create"
                                        :disabled (:submitted state)}})]])))))

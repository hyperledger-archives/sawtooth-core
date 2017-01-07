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

(ns bond.components.participant-update
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.state :refer [app-state]]
            [sawtooth.ledger.keys :refer [address get-key-pair]]
            [sawtooth.components.core :as saw :include-macros]
            [sawtooth.router :as router]
            [bond.routes :as routes]
            [bond.transactions :refer [update-participant modify-authorization]]
            [bond.components.core :as core]))

(defn- is-valid? [{:keys [username firm-id firm-role]}]
  (and (not (empty? username))
       firm-id
       firm-role))

(defn- populate-state [{participant :participant} owner]
  (let [{:keys [username firm-id firm-role]} participant
        owner-state! (partial om/set-state! owner)]
    (owner-state! :username username)
    (owner-state! :firm-id firm-id)
    (owner-state! :firm-role firm-role)
    (owner-state! :original-role firm-role)))

(defn- firm-option [{:keys [id name pricing-source]}]
  [:option {:key id :value id} (str name " (" pricing-source ")")])

(defn- send-update
  [{:keys [username firm-id firm-role original-role] :as state}
   {participant :participant orgs :organizations} owner]

  (if (is-valid? state)
    (let [id (:id participant)
          username (if (not= username (:username participant)) username nil)
          firm-changed (not= firm-id (:firm-id participant))
          role-changed (not= firm-role original-role)]
      (om/set-state! owner :submitted true)

      (when (or username firm-changed)
        (update-participant (get-key-pair) {:object-id id
                                            :username username
                                            :firm-id (when firm-changed firm-id)}))

      (when (or firm-changed role-changed)
        (modify-authorization (get-key-pair) id
                              (:firm-id participant) firm-id
                              original-role firm-role))

      (router/push (routes/home-path)))
    (core/invalid-tip! "Update")))

(defn participant-update-form [data owner]
  (let [trading-orgs (filter core/trading-firm? (:organizations data))
        owner-field (partial saw/text-field owner)]
    (reify
      om/IWillMount
      (will-mount [_]
        (populate-state data owner))

      om/IWillReceiveProps
      (will-receive-props [_ next-props]
        (populate-state next-props owner))

      om/IRenderState
      (render-state [_ state]
        (html
          [:div.container
           (core/heading "Update Participant")
           [:form.form.participant-update-form
            {:ref "update-participant"
             :on-submit (saw/handle-submit owner "update-participant"
                                           (send-update state data owner))}

            (core/form-section "Participant Info" "participant-info"
                               (owner-field :username "Name" {:required true}))

            (core/form-section "Authorization" "participant-auth"
                               (core/divided-rows
                                 (saw/select-field owner :firm-id "Firm"
                                                   (map firm-option trading-orgs))
                                 (saw/select-field owner :firm-role "Role"
                                                   [[:option {:key 0 :value "marketmaker"} "Market Maker"]
                                                    [:option {:key 1 :value "trader"} "Trader"]])))

            (saw/form-buttons owner {}
                              {:submit {:label "Update"
                                        :disabled (:submitted state)}})]])))))

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

(ns bond.components.participant-form
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.state :refer [app-state]]
            [sawtooth.ledger.keys :refer [get-key-pair clear-wif!]]
            [sawtooth.components.core :refer [text-field select-field form-buttons]
                                      :refer-macros [handle-event when-new-block]]
            [sawtooth.router :as router]
            [bond.routes :as routes]
            [bond.transactions :refer [create-participant]]
            [bond.service.organization :refer [organizations!]]
            [bond.components.core :refer [form-section divided-rows heading trading-firm? invalid-tip!]]))

(defn- is-valid? [state]
  (reduce #(and %1 (not (empty? (%2 state)))) true
               [:username :firm]))

(defn- firm-option [{:keys [object-id name]}]
  [:option {:key object-id :value object-id} name])

(defn- submit-handler [state owner]
  (if (is-valid? state)
    (do (om/set-state! owner :submitted true)
        (create-participant
          (get-key-pair)
          (:username state)
          (:firm state)
          #(router/push (routes/home-path))))
    (invalid-tip! "Create Participant" "Form is invalid. Did you select a Firm?")))

(defn participant-form [data owner]
  (let [owner-field (partial text-field owner)]
    (reify
      om/IWillMount
      (will-mount [_] (organizations!))

      om/IWillReceiveProps
      (will-receive-props [_ next-state]
        (when-new-block owner next-state (organizations!)))

      om/IRenderState
      (render-state [_ state]
        (html
          [:div.container
           (heading "Create Participant")
           [:form.form.participant-form {:on-submit (handle-event (submit-handler state owner))}

            (form-section "Participant Info" "participant"
                          (divided-rows
                            (owner-field :username "Username" {:required true})
                            (select-field owner :firm "Firm"
                                          (->> (:organizations data)
                                               (filter trading-firm?)
                                               (map firm-option)
                                               (conj [[:option {:key 0} "Select a Firm..."]]))
                                          {:required true})))

	          (form-buttons owner {}
                         {:submit {:label "Create Participant"
                                   :disabled (:submitted state)}
                          :reset {:label "Cancel"
                                  :on-click (handle-event
                                              (clear-wif!)
                                              (router/push (routes/home-path)))}})]])))))

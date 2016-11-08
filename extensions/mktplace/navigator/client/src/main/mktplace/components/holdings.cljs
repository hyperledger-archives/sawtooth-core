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
(ns mktplace.components.holdings
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [taoensso.timbre :as timbre
             :refer-macros [infof]]
            [sawtooth.ledger.keys :as keys]
            [sawtooth.components.core
             :refer [glyph form-buttons text-field select-field ->int]
             :refer-macros [handle-event]]
            [mktplace.components.format :as fmt]
            [mktplace.transactions]))

(defn- is-valid-asset? [asset]
  (and asset (not= asset :unselected)))

(defn- is-valid?
  [{:keys [name asset count]}]
  (and (is-valid-asset? asset)
       (fmt/valid-object-name? name)
       (>= count 0)))


(defn- can-add-instances?
  [{participant-id :id} {:keys [creator restricted] :as asset}]
  (and (is-valid-asset? asset)
       (or (= participant-id creator)
           (not restricted))))

(defn- asset-option [{:keys [id] :as asset}]
  (html
    [:option {:key id :value id} (fmt/object-name asset)]))

(defn holding-form [data owner]
  (let [selected-asset (get-in data [:selections :asset])
        initial-state {:count 0 :asset selected-asset}
        empty-option (html [:option {:key 0 :value :unselected} "Select an Asset"])]
    (reify
      om/IInitState
      (init-state [_] initial-state)

      om/IRenderState
      (render-state [_ state]
        (let [{:keys [participant assets]} data
              asset-options (conj [empty-option]
                                  (map #(asset-option %) (sort-by :name assets)))
              submit-handler (handle-event
                               (when (is-valid? state)
                                 (infof "submitting %s" state)
                                 (mktplace.transactions/register-holding
                                   (keys/get-key-pair)
                                   participant
                                   state)
                                 (om/set-state! owner initial-state)))]
          (html
            [:div
             [:h3 "Create Holding"]

             [:form.form.holding-form {:on-submit submit-handler}
              (text-field owner :name "Name"
                          {:help-text "An optional, human-readable name for
                                      the holding. Must begin with '/'."
                           :pattern fmt/object-name-pattern})

              (text-field owner :description "Description"
                          {:help-text "Optional information about the holding."})

              (select-field owner :asset "Asset" asset-options
                            {:parse-fn (fn [id] (->> assets (filter #(= id (:id %))) first))
                             :value (get-in state [:asset :id] :unselected)})

              (text-field owner :count "Count"
                          {:type "number"
                           :min 0
                           :parse-fn ->int
                           :disabled (not (can-add-instances? participant (:asset state)))})

              (form-buttons owner initial-state
                            {:submit {:disabled (not (is-valid? state))}})]]))))))

(defn holding-detail
  "Component for dispaying the holding details"
  [{:keys [assets holding participant-name]} owner]
  (om/component
    (let [holding-name (fmt/object-name holding)
          holding-type
          (fmt/asset-name-by-holding assets holding)
          amount (get holding :count)]
      (html
        [:div
         (when participant-name
           [:span.participant-name participant-name])
         [:table.holding-entry
          [:tbody
           [:tr
            [:td
             [:span.holding-name holding-name]
             [:br]
             [:span.holding-type holding-type]]
            [:td.holding-count {:class (if (> 0 amount) "text-danger")}
             amount]]]]]))))

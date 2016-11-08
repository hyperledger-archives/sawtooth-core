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
(ns mktplace.components.assets
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [taoensso.timbre :as timbre
             :refer-macros [infof]]
            [sawtooth.ledger.keys :as keys]
            [sawtooth.components.core
             :refer [glyph form-buttons text-field select-field check-box-field]
             :refer-macros [handle-event]]
            [mktplace.components.format :as fmt]
            [mktplace.transactions]))

(defn- asset-type-options [participant-id asset-types]
  (html
    (let [options (->> asset-types
                       (filter #(or (= participant-id (:creator %))
                                     (not (:restricted %))))
                       (sort-by :name)
                       (map #(let [{:keys [id name]} %]
                               [:option {:key id :value id} name])))]
      (conj [[:option {:key "unselected"} "Select an Asset Type"]]
            (if (empty? options)
              [:option {:key "none"} "No Asset Types Available"]
              options)))))

(defn- is-valid-asset-type? [new-asset-type]
  (and new-asset-type
       (fmt/valid-object-name? (:name new-asset-type))))

(defn- is-valid?
  [{:keys [name asset-type new-asset-type]}]
  (and (or asset-type
           (is-valid-asset-type? new-asset-type))
       (fmt/valid-object-name? name)))

(defn- submit-asset [participant state]
  (mktplace.transactions/register-asset
    (keys/get-key-pair)
    participant
    (or (:asset-type state) (:new-asset-type state))
    (dissoc state :new-asset-type :asset-type)))

(defn- reset-form! [owner initial-state]
  (.reset (om/get-ref owner "asset-form"))
  (om/set-state! owner initial-state))

(defn asset-form [data owner]
  (let [initial-state {:consumable true
                       :restricted true}
        initial-new-asset-type {:restricted true}]
    (reify
      om/IInitState
      (init-state [_] initial-state)

      om/IRenderState
      (render-state [_ state]
        (let [participant (:participant data)
              asset-types (asset-type-options (:id participant) (:asset-types data))
              submit-handler (handle-event
                               (infof "submitting asset %s" state)
                               (submit-asset participant state)
                               (reset-form! owner initial-state))
              reset-handler (handle-event
                              (reset-form! owner initial-state)) ]
          (html
            [:div
             [:h3 "Create Asset"]

             [:form.form.asset-form {:on-submit submit-handler
                                     :ref "asset-form"}
              (text-field owner :name "Name"
                          {:help-text "An optional, human-readable name for the
                                      asset. Must begin with '/'."
                           :pattern fmt/object-name-pattern})

              (text-field owner :description "Description"
                          {:help-text "Optional information about the asset."})

              (select-field owner :asset-type "Type" asset-types
                            {:disabled (:new-asset-type state)
                             :peer (html
                                     [:button.btn.btn-default
                                      {:disabled (:new-asset-type state)
                                       :on-click (handle-event
                                                   (om/set-state! owner :new-asset-type initial-new-asset-type))}
                                      (glyph :plus) " Add Type"])})

              (when (:new-asset-type state)
                [:div.panel.panel-default
                 [:div.panel-heading "Create Asset Type"]
                 [:div.panel-body
                  (text-field owner [:new-asset-type :name] "Name"
                              {:help-text "An optional, human-readable name
                                          for the asset type. Must begin with
                                          '/'."
                               :pattern fmt/object-name-pattern})

                  (text-field owner [:new-asset-type :description] "Description"
                              {:help-text "Optional information about the asset type."})

                  (check-box-field owner [:new-asset-type :restricted ] "Restricted"
                                   {:help-text "Only the creator of the asset type may
                                               create assets of this type."})

                  [:div.form-button-group
                   [:button.btn.btn-default.pull-right
                    {:on-click (handle-event
                                 (om/set-state! owner :new-asset-type nil))}
                    "Discard"]]

                  ]])

              (check-box-field owner :restricted "Restricted")
              (check-box-field owner :consumable "Consumable")
              (check-box-field owner :divisible "Divisible")

              (form-buttons owner initial-state
                            {:submit {:disabled (not (is-valid? state))}})]]))))))

(defn asset-detail [{:keys [asset-types asset]} owner]
  (om/component
    (let [asset-name (fmt/object-name asset)
          asset-type-name (fmt/asset-type-name-by-asset asset-types asset)]
      (html
        [:div
         [:span.asset-name asset-name]
         [:br]
         [:span.asset-type asset-type-name]]))))

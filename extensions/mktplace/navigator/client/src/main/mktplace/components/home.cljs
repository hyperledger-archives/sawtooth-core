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
(ns mktplace.components.home
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [goog.string :as gstring]
            [sawtooth.router :as router]
            [sawtooth.components.core :refer-macros [when-changed when-diff]]
            [mktplace.service.asset :as asset]
            [mktplace.service.selection :as selection-svc]
            [mktplace.components.portfolio :as portfolio]
            [mktplace.service.participant :as participant-service]))

(defn- load-assets!
  []
  (asset/assets))

(defn- load-view-participant! [{[_ {view-participant-id :participant-id}] :route}]
  (when view-participant-id
    (participant-service/as-participant view-participant-id)))

(defn home [data owner]
  (reify
    om/IDisplayName
    (display-name [_] "Home")

    om/IWillMount
    (will-mount [_]
      (load-assets!)
      (load-view-participant! data))

    om/IWillReceiveProps
    (will-receive-props [_ next-state]

      (when-changed owner next-state [:block]
        (load-assets!)
        (load-view-participant! next-state))

      (when-diff owner next-state #(let [{[_ {:keys [participant-id]}] :route} %]
                                     participant-id)
        (selection-svc/select-holding! nil)
        (load-view-participant! next-state)))

    om/IRender
    (render [_]
      (let [participant (get data :participant)
            view-participant (or (get data :view-participant)
                                 participant)]
        (html
          (cond
            (:pending participant)
            [:div.container
             [:h3 "Waiting for participant to be provisioned.

                  This may take a few minutes..."]]

            (not (participant-service/is-fully-provisioned? participant))
            [:div.container
             [:h3 "Participant provisioned. Registering an account.

                  This may take a few minutes..."]]

            :default
            [:div.container-fluid
             [:div.row
              [:div.col-sm-5.col-md-5.sidebar
               [:p (if (= (get view-participant :id) (get participant :id))
                     "My Portfolio"
                     (gstring/format "%s's Portfolio" (get view-participant :name)))]

               (let [{:keys [assets asset-types selections]} data
                     holdings (if (get selections :asset)
                                (filter #(= (:asset %) (get-in selections [:asset :id]))
                                        (:holdings view-participant))
                                (:holdings view-participant))]
               (om/build portfolio/portfolio  {:assets assets
                                               :asset-types asset-types
                                               :holdings holdings
                                               :selections selections}))]
              [:div.col-sm-7.col-sm-offset-5.col-md-7.col-md-offset-5.main
               (router/route-handler data owner)]]]))))))

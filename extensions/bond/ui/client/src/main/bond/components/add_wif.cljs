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

(ns bond.components.add-wif
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.state :refer [app-state]]
            [sawtooth.components.core
             :refer [basic-text-field form-buttons upload-text-button]
             :refer-macros [handle-event]]
            [sawtooth.ledger.keys :refer [save-wif!]]
            [sawtooth.utils :refer [browser]]
            [sawtooth.router :as router]
            [bond.routes :as routes]
            [bond.components.core :refer [heading boot-row]]))

(defn is-valid? [state]
  (:wif-key state))

(defn add-wif [data owner]
  (reify
    om/IRenderState
    (render-state[_ state]
      (html
        [:div.container.add-wif
         (heading "Import WIF Key")
         [:form.form.add-wif-form
          {:automcomplete "off"
           :on-submit (handle-event
                        (save-wif! (:wif-key state))
                        (router/replace (routes/home-path)))}

         [:div.panel.panel-primary
          [:div.panel-heading "Input your WIF key"]
          [:div.panel-body "Either copy and paste your WIF key below,
                           or upload the \".wif\" file you downloaded earlier."]
          [:div.panel-footer

           (boot-row "text-center"
                     (basic-text-field owner :wif-key {:type "password"
                                                       :placeholder "Paste WIF key..."})

                     [:span.has-tip.show-on-hover
                      (upload-text-button owner :wif-key "Upload WIF File"
                                          {:disabled (= :firefox (browser))})
                      (when (= :firefox (browser))
                        [:span.tip-text "Uploading not supported on Firefox"])])]]

         (form-buttons owner {}
                       {:submit {:disabled (not (is-valid? state))
                                 :class "btn-lg"}
                          :reset {:label "Cancel"
                                 :class "btn-lg"
                                  :on-click (handle-event
                                              (router/replace (routes/home-path)))}})]]))))

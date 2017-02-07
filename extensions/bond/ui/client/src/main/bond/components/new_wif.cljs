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

(ns bond.components.new-wif
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.state :refer [app-state]]
            [sawtooth.ledger.keys :as wif]
            [sawtooth.router :refer [replace]]
            [sawtooth.files :refer [text-file-url!]]
            [sawtooth.utils :refer [browser]]
            [sawtooth.service.common :refer [set-path!]]
            [sawtooth.components.tooltip :refer [timed-tip! keyup-tip!]]
            [sawtooth.vendor :refer [Clipboard]]
            [bond.components.core :refer [boot-row] :as core]
            [bond.routes :as routes]))

(defn- copy-success [e]
  (timed-tip! (.-trigger e) "Copied!"))

(defn- copy-failure [e]
  (keyup-tip! (.-trigger e) core/copy-fail-msg))

(defn new-wif [data owner]
  (let [set-state! (partial om/set-state! owner)
        set-wif-saved! #(set-state! :wif-saved true)]
    (reify
      om/IDidMount
      (did-mount [_]
        (let [key-pair (wif/random-key-pair)
              wif-key (wif/key-pair->wif key-pair)
              wif-url (text-file-url! wif-key)
              clipboard (Clipboard. ".btn-copy")]
          (set-state! :wif-key wif-key)
          (set-state! :wif-url wif-url)
          (set-path! [:key-pair] key-pair)
          (wif/save-wif! wif-key)
          (.on clipboard "success" copy-success)
          (.on clipboard "error" copy-failure)))

      om/IRenderState
      (render-state [_ state]
        (html
          [:div.container.new-wif
           (core/heading "Generate WIF Key")

           [:div.panel.panel-primary
            [:div.panel-heading "Key Generated!"]
            [:div.panel-body "To continue, download your key or copy and paste
                             it. There is no way to recover your identity if
                             this key is lost. Keep it in a safe place!"]
            [:div.panel-footer

             (boot-row "text-center"
                       [:span.has-tip.show-on-hover
                        [:a.btn.btn-primary
                         {:href (:wif-url state)
                          :download "participant.wif"
                          :on-click set-wif-saved!
                          :disabled (= :safari (browser))}
                          "Download Key"]
                        (when (= :safari (browser))
                          [:span.tip-text "Downloading not supported on Safari"])]

                        [:a.btn.btn-primary.btn-copy
                          {:data-clipboard-text (:wif-key state)
                           :on-click set-wif-saved!}
                          "Copy Key to Clipboard"])]]

           [:div
            [:button.btn.btn-primary.btn-lg
             {:on-click #(replace (routes/participant-form))
              :disabled (not (:wif-saved state))}
             "Create Participant"]]])))))

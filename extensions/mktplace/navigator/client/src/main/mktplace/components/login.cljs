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
(ns mktplace.components.login
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [cljs.core.async :as async :refer [put!]]
            [sawtooth.ledger.keys :as keys]
            [sawtooth.router :as router]
            [sawtooth.service.block :as block]
            [sawtooth.service.common :as svc]
            [sawtooth.files :as files]
            [sawtooth.components.core :as components
             :refer [glyph text-field form-buttons link-button boot-row]
             :refer-macros [handle-event handle-submit handler when-new-block]]
            [sawtooth.components.tooltip :refer [timed-tip! keyup-tip!]]
            [sawtooth.utils :as utils]
            [sawtooth.vendor :refer [Clipboard]]
            [mktplace.routes :as routes]
            [mktplace.service.participant :as participant]
            [mktplace.components.header :refer [header]]))

(defn- is-valid? [{:keys [participant-name]}]
 (and participant-name (not (empty? participant-name))))

(defn create-participant [{:keys [route]} owner]
  (reify
    om/IInitState
    (init-state [_] {})

    om/IRenderState
    (render-state [_ {:keys [participant-name participant-description] :as state}]
      (let [[_  {:keys [address]}] route
            submit-handler (handle-submit owner "participant-form"
                             (participant/register
                               (keys/get-key-pair)
                               address
                               participant-name
                               participant-description))
            cancel-handler (handle-event
                             (keys/clear-wif!)
                             (router/push (routes/intro-path)))]
        (html
          [:div.container
           [:h2 "Create a Participant"]

           [:form.form-horizontal.create-particiant-form
            {:on-submit submit-handler
             :ref "participant-form"}

            (text-field owner :participant-name "Name"
                        {:required true})

            (text-field owner
                        :participant-description
                        (components/header-note "Description" "optional"))

            (form-buttons owner {}
                          {:submit {:disabled (not (is-valid? state))}
                           :reset {:label "Cancel"
                                   :on-click cancel-handler}})]])))))

(defn intro [data owner]
  (reify
    om/IRenderState
    (render-state [_ {:keys [show-settings?]}]
      (html
        [:div.container
         [:div.text-center
          [:h1 "Welcome to Marketplace Navigator"]
          [:p "Marketplace Navigator is a simple proof-of-concept asset
              exchange built on top of the Sawtooth Lake distrubted ledger,
              and is "
              [:a {:href "http://intelledger.github.io/mktnav_users_guide.html"
                   :target "_blank"}
               "documented here"]
              "."]
          [:p "To begin you will need to create an identity by generating a new
              Wallet Import Format (WIF) key or importing an existing one."]]
         [:div.panel.panel-warning
          [:div.panel-heading "Generate or import your WIF key:"]
          [:div.panel-footer
           (boot-row "text-center"
                     (link-button (routes/new-wif-path) "Generate WIF" {:btn-type :warning})
                     (link-button (routes/add-wif-path) "Import WIF" {:btn-type :warning}))]]]))))

(defn- load-participant-info [address]
  (participant/participants)
  (participant/participant-by-address address))

(defn- on-authed-component-mount [wallet-id]
  (load-participant-info wallet-id)
  (block/connect-block-monitor))

(defn- do-fetch-on-wallet [fetch-fn]
  (if-let [address (-> (keys/get-key-pair) (keys/address))]
    (fetch-fn address)
    (router/replace (routes/intro-path))))


(defn authed-component
  "This component requires authentication"
  [data owner]
  (reify
    om/IWillMount
    (will-mount [_]
      (do-fetch-on-wallet on-authed-component-mount))

    om/IWillReceiveProps
    (will-receive-props [_ next-state]
      (when-new-block owner next-state
        (do-fetch-on-wallet load-participant-info)))

    om/IWillUnmount
    (will-unmount [_]
      (block/disconnect-block-monitor))

    om/IRender
    (render [_]
      (html
        (let [{:keys [participant]} data]
          (if participant
            [:div
             (om/build header (select-keys data [:participant :block]))
             (router/route-handler data owner)]
            [:div.container "Loading..."]))))))

(defn add-wif [data owner]
  (letfn [(is-valid? [state] (:wif-key state))]
    (reify
      om/IRenderState
      (render-state [_ state]
        (html
          [:div.container.add-wif
           [:h1 "Import WIF Key"]
           [:form.form.add-wif-form
            {:autocomplete "off"
             :on-submit (handle-event
                          (keys/save-wif! (:wif-key state))
                          (router/replace (routes/home-path)))}

           [:div.panel.panel-primary
            [:div.panel-heading "Input your WIF key"]
            [:div.panel-body "Either copy and paste your WIF key below,
                             or upload the \".wif\" file you downloaded earlier."]
            [:div.panel-footer

             (boot-row "text-center"
               (components/basic-text-field owner :wif-key
                                            {:type "password"
                                             :placeholder "Paste WIF key..."})

               [:span.has-tip.show-on-hover
                (components/upload-text-button owner :wif-key "Upload WIF File")])]]

           (form-buttons owner {}
                         {:submit {:disabled (not (is-valid? state))
                                   :class "btn-lg"}
                            :reset {:label "Cancel"
                                   :class "btn-lg"
                                    :on-click (handle-event
                                                (router/replace (routes/home-path)))}})]])))))

(def copy-fail-msg
  (cond (re-find #"iPhone|iPad" (.-userAgent js/navigator))
        "Copying unsupported on iOS"
        (re-find #"Mac" (.-userAgent js/navigator))
        "Press ⌘-C to Copy"
        :default
        "Press Ctrl-C to Copy"))

(defn- copy-success [e]
  (timed-tip! (.-trigger e) "Copied!"))

(defn- copy-failure [e]
  (keyup-tip! (.-trigger e) copy-fail-msg))

(defn new-wif [data owner]
  (let [set-state! (partial om/set-state! owner)
        set-wif-saved! #(set-state! :wif-saved true)]
    (reify
      om/IDidMount
      (did-mount [_]
        (let [key-pair (keys/random-key-pair)
              wif-key (keys/key-pair->wif key-pair)
              wif-url (files/text-file-url! wif-key)
              clipboard (Clipboard. ".btn-copy")]
          (set-state! :wif-key wif-key)
          (set-state! :wif-url wif-url)
          (svc/set-path! [:key-pair] key-pair)
          (keys/save-wif! wif-key)
          (.on clipboard "success" copy-success)
          (.on clipboard "error" copy-failure)))

      om/IRenderState
      (render-state [_ state]
        (html
          [:div.container.new-wif
           [:h1 "Generate WIF Key"]

           [:div.panel.panel-primary
            [:div.panel-heading "Key Generated!"]
            [:div.panel-body "To continue, download your key or copy and paste
                             it. There is no way to recover your identity if
                             this key is lost, so keep it in a safe place!"]
            [:div.panel-footer

             (boot-row "text-center"
               [:span.has-tip.show-on-hover
                [:a.btn.btn-primary
                 {:href (:wif-url state)
                  :download "mktplace.wif"
                  :on-click set-wif-saved!
                  :disabled (= :safari (utils/browser))}
                  "Download Key"]
                (when (= :safari (utils/browser))
                  [:span.tip-text "Downloading not supported on Safari"])]

                [:a.btn.btn-primary.btn-copy
                  {:data-clipboard-text (:wif-key state)
                   :on-click set-wif-saved!}
                  "Copy Key to Clipboard"])]]

           [:div
            [:button.btn.btn-primary.btn-lg
             {:on-click (handle-event
                          (router/replace (routes/create-participant-path
                                            {:address (keys/address (:key-pair data))})))
              :disabled (not (:wif-saved state))}
             "Create Participant"]]])))))

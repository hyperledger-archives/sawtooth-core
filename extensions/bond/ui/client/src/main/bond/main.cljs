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

(ns bond.main
  (:require [om.core :as om :include-macros true]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.router :as router]
            [sawtooth.state :refer [app-state]]
            [sawtooth.events :refer [on-content-loaded]]
            [sawtooth.service.block :as block]
            [sawtooth.components.notification :refer [notification-container]]
            [sawtooth.components.block :refer [transaction-history]]
            [bond.routes :as routes]
            [bond.components.description :refer [landing-description]]
            [bond.components.auth :refer [welcome auth-header authenticated-component]]
            [bond.components.footer :refer [footer]]
            [bond.components.new-wif :refer [new-wif]]
            [bond.components.add-wif :refer [add-wif]]
            [bond.components.quote-form :refer [quote-form]]
            [bond.components.order-form :refer [order-form]]
            [bond.components.quote-list :refer [quote-list]]
            [bond.components.order-list :refer [order-list]]
            [bond.components.bond-list :refer [bond-list]]
            [bond.components.bond-detail :refer [bond-detail]]
            [bond.components.bond-form :refer [bond-form]]
            [bond.components.portfolio :refer [portfolio]]
            [bond.components.holding-list :refer [holdings-list]]
            [bond.components.receipt-list :refer [receipts-list]]
            [bond.components.settlement-list :refer [settlements-list]]
            [bond.components.participant-form :refer [participant-form]]
            [bond.components.participant-update :refer [participant-update-form]]
            [bond.components.org-form :refer [org-form]]))

(enable-console-print!)


(defn not-found [_ owner]
  (om/component
    (html
      [:div
       [:nav.navbar.navbar-default.navbar-fixed-top
        [:div.container-fluid
        [:div.navbar-header
         [:a.navbar-brand {:href (routes/home-path)} "Sawtooth Bond"]]]]
      [:div.container
       [:h1 "Not found"]
       [:p [:a {:href (routes/home-path)} "Go Home"]]]])))

(defn home [data owner]
  (om/component
    (html
      [:div.container
       [:h1 "Sawtooth Bond"]
       (if-not (get-in data [:participant :pending])
         (landing-description)
         [:div.panel.panel-warning
          [:div.panel-heading "Creating and Authorizing Your Participant"]
          [:div.panel-body
           "Transactions have been submitted to create your participant and
           authorize it with your choosen firm. Once everything is committed,
           you will be able to interact with the Sawtooth Bond system."]])])))

(defn app [data owner]
  (om/component
    (html
      [:div
       [:div.main-content
         (router/route-handler data owner)]
       (om/build footer {:block (:block data)})
       [:div
        (om/build notification-container (select-keys data [:notification]))]])))

(defn block-monitor [data owner]
  (reify
    om/IWillMount
    (will-mount [_] (block/connect-block-monitor))

    om/IWillUnmount
    (will-unmount [_] (block/disconnect-block-monitor))

    om/IRender
    (render [_]
      (router/route-handler data owner))))

(defn route-components []
  {:home [block-monitor auth-header authenticated-component home]
   :transaction-history [block-monitor authenticated-component transaction-history]
   :not-found [not-found]
   :welcome [welcome]
   :new-wif [new-wif]
   :add-wif [add-wif]
   :quote-form [block-monitor auth-header authenticated-component quote-form]
   :order-form [block-monitor auth-header authenticated-component order-form]
   :quote-list [block-monitor auth-header authenticated-component quote-list]
   :order-list [block-monitor auth-header authenticated-component order-list]
   :bond-detail [block-monitor auth-header authenticated-component bond-detail]
   :bond-list [block-monitor auth-header authenticated-component bond-list]
   :bond-form [block-monitor auth-header authenticated-component bond-form]
   :org-form [block-monitor auth-header authenticated-component org-form]
   :portfolio-holdings [block-monitor auth-header authenticated-component portfolio holdings-list]
   :portfolio-receipts [block-monitor auth-header authenticated-component portfolio receipts-list]
   :portfolio-settlements [block-monitor auth-header authenticated-component portfolio settlements-list]
   :participant-form [block-monitor participant-form]
   :participant-update [block-monitor auth-header authenticated-component participant-update-form]})

(defn start-app []
  (when-let [app-el (. js/document (getElementById "app"))]
    (swap! app-state merge {:route [:home]})

    (router/initialize-route (routes/home-path))

    (om/root
      app
      app-state
      {:target app-el
       :shared {:current-route router/current-route
                :route-components route-components
                :not-found not-found}})))

(on-content-loaded start-app)

(defn on-reload []
  (swap! app-state assoc-in [:route 1 :__timestamp] (.now js/Date)))

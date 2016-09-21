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
(ns mktplace.main
  (:require [om.core :as om :include-macros true]
            [cljs.core.async :as async :refer [put!]]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.state :refer [app-state]]
            [sawtooth.router :as router]
            [sawtooth.events :refer [on-content-loaded]]
            [sawtooth.components.notification :refer [notification-container]]
            [sawtooth.components.block :refer [transaction-history]]
            [mktplace.routes :as routes]
            [mktplace.components.login :as login
             :refer [intro create-participant authed-component]]
            [mktplace.components.home :refer [home]]
            [mktplace.components.dashboard :refer [dashboard]]
            [mktplace.components.portfolio :refer [portfolio-summary]]
            [mktplace.components.assets :refer [asset-form]]
            [mktplace.components.holdings :refer [holding-form]]
            [mktplace.components.exchanges :refer [exchanges exchange-form transfer-form]]
            [mktplace.components.offers :refer [offers sell-offer-form]]))

(enable-console-print!)

(defn not-found [_ owner]
  (om/component
    (html
      [:div.container-fluid
       [:h3 "Not Found"]
       [:p "I'm sorry, I don't know where you want to be."]])))

(defn app [data owner]
  (om/component
    (html
      [:div
       (router/route-handler data owner)
       [:div
        (om/build notification-container (select-keys data [:notification]))]])))

(defn route-components []
  {:home [authed-component home dashboard]
   :exchanges [authed-component home exchanges]
   :offers [authed-component home offers]
   :sell-offer-form [authed-component home sell-offer-form]
   :exchange [authed-component home exchange-form]
   :transfer [authed-component home transfer-form]
   :asset-form [authed-component home asset-form]
   :holding-form [authed-component home holding-form]
   :portfolio [authed-component portfolio-summary]
   :block-transactions [authed-component transaction-history]
   :intro [intro]
   :add-wif [login/add-wif]
   :new-wif [login/new-wif]
   :create-participant [create-participant]
   :not-found [not-found]})

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

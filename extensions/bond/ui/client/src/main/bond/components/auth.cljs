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

(ns bond.components.auth
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.state :refer [app-state]]
            [sawtooth.ledger.keys :refer [address get-key-pair]]
            [sawtooth.utils :refer [browser]]
            [sawtooth.router :as router]
            [sawtooth.components.core
             :refer-macros [when-new-block handle-event]]
            [bond.routes :as routes]
            [bond.service.participant :as participant-svc]
            [bond.service.organization :as org-svc]
            [bond.components.core :refer [heading boot-row link-button]]))

(defn- load-participant []
  (if-let [key-pair (get-key-pair)]
    (let [address (address key-pair)]
      (participant-svc/participant! address {:fetch-firm true} #(router/replace (routes/participant-form))))
    (router/replace (routes/welcome))))

(defn welcome [data owner]
  (reify
    om/IRenderState
    (render-state [_ state]
      (html
        [:div.container.welcome
         [:div.page-header.text-center
          (heading "Welcome to Sawtooth Bond")
          [:p "Sawtooth Bond is a proof-of-concept bond trading platform,
              built on the Sawtooth Lake distributed ledger."]
          [:p "To begin you will need to create an identity by generating a new
              Wallet Import Format (WIF) key or importing an existing one."]
           (when (or (= :edge (browser)) (= :ie (browser)) (not (browser)))
            [:div.row
             [:div.alert.alert-danger.col-md-10.col-md-offset-1
              {:role "alert"}
              [:span.glyphicon.glyphicon-exclamation-sign {:aria-hidden true}]
              (cond
                (= :edge (browser)) " Microsoft Edge is not supported for this demo."
                (= :ie (browser)) " Internet Explorer is not supported for this demo."
                :default " Your browser configuration could not be detected.")
              " We recommend using Google Chrome for the best experience."]])]
         [:div.panel.panel-warning
          [:div.panel-heading "Generate or import your WIF key:"]
          [:div.panel-footer
           (boot-row "text-center"
                     (link-button (routes/new-wif) "Generate WIF" {:btn-type :warning})
                     (link-button (routes/add-wif) "Import WIF" {:btn-type :warning}))]]]))))

(defn auth-header [data owner]
  (reify
    om/IWillMount
    (will-mount [_] (load-participant))

    om/IWillReceiveProps
    (will-receive-props [_ next-state]
      (when-new-block owner next-state (load-participant)))

    om/IRender
    (render [_]
      (if (:participant data)
        (router/route-handler data owner)
        (html
          [:div.container "Loading..."])))))

(defn- nav-link [data _]
  (om/component
    (let [{:keys [href label linked-route ]} data
          linked-route (if (vector? linked-route) (set linked-route) #{linked-route})
          current-route (get-in data [:current 0])]
      (html
        [:li {:class (if (get linked-route current-route) "active")}
         [:a {:href href} label]]))))

(defn make-nav-link
  [data k label href]
  (om/build nav-link {:current (:route data)
                      :linked-route k
                      :label label
                      :href href}))

(defn authenticated-component [data owner]
 (reify
   om/IWillMount
   (will-mount [_]
     (org-svc/organizations!))

   om/IWillReceiveProps
   (will-receive-props [_ next-state]
     (when-new-block owner next-state
       (org-svc/organizations!)))

   om/IRender
   (render [_]
     (let [username (get-in data [:participant :username])]
       (html
         [:div
          [:nav.navbar.navbar-default.navbar-fixed-top
           [:div.container-fluid
            [:div.navbar-header
             [:button.navbar-toggle.collapsed {:type "button"}]
             [:a.navbar-brand {:href (routes/home-path)} "Sawtooth Bond"]]
            (when (:participant data)
              [:div
               (when-not (get-in data [:participant :pending])
                 [:ul.nav.navbar-nav
                  (make-nav-link data :bond-list "Bonds" (routes/bond-list))
                  (make-nav-link data :bond-form "Create Bond" (routes/bond-form))
                  (make-nav-link data :order-list "Orders" (routes/order-list))
                  (make-nav-link data :quote-form "Issue Quote" (routes/quote-form))
                  (make-nav-link data :org-form "Create Organization" (routes/org-form))
                  (make-nav-link data [:portfolio-holdings :portfolio-receipts :portfolio-settlements]
                                 "Portfolio" (routes/portfolio))])

               [:ul.nav.navbar-nav.navbar-right
                [:li
                 [:p.navbar-text "Hello, "
                  [:a.navbar-link {:href (routes/participant-update)} [:strong username]]]]
                [:li
                 [:a {:href "#"
                      :on-click (handle-event
                                  (participant-svc/sign-out!
                                    #(router/push (routes/welcome))))}
                      "Sign Out"]]]])]]
         (router/route-handler data owner)])))))

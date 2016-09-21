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
(ns mktplace.components.header
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.router :as router]
            [sawtooth.components.core
             :refer [glyph dropdown]
             :refer-macros [handle-event]]
            [mktplace.routes :as routes]
            [mktplace.service.participant :as participant-service]))


(defn- toggle-menu
  ([owner] (toggle-menu owner (not (om/get-state owner :menu-open))))
  ([owner open?]
   (om/set-state! owner :menu-open open?)))

(defn- menu-item [owner label link-or-action-fn]
  [:li [:a {:href (if (string? link-or-action-fn)
                   link-or-action-fn  "#")
            :on-click (fn [e]
                        (toggle-menu owner false)
                        (when (fn? link-or-action-fn)
                          (.preventDefault e)
                          (link-or-action-fn)))}
        label]])

(defn header
  "Marketplace header component."
  [{participant :participant {:keys [blocknum blockid] :as block} :block} owner]
  (om/component
    (let [participant-name (if (not= (:name participant) "")
                             (:name participant)
                             (:id participant))
          link-args {:participant-id (participant-service/current-participant-id)}]
      (html [:nav.navbar.navbar-inverse.navbar-fixed-top
             [:div.navbar-header
              [:a.navbar-brand {:href (routes/dashboard-path link-args)}
               "Ledger Explorer"]]
             [:div#navbar
              [:ul.nav.navbar-nav.navbar-right
               (when block
                 [:li [:a {:href (routes/block-transactions-path)}
                       (str "Block: " blocknum " (" blockid ")")]])

               (when (participant-service/is-fully-provisioned? participant)
                 [:li [:a {:href (routes/sell-offer-path)}
                       [:span (glyph :plus) " Create Offer"]]])

               [:li.dropdown {:class (if (om/get-state owner :menu-open) "clearfix open")}
                [:a.dropdown-toggle {:href "#"
                                     :on-click (handle-event (toggle-menu owner))}
                 (str "Hi, " participant-name)
                 [:span.caret]]
                [:ul.dropdown-menu
                 [:li.divider {:role "separator"}]
                 (menu-item owner "Dashboard" (routes/dashboard-path link-args))
                 (menu-item owner "Portfolio" (routes/portfolio-path link-args))
                 (menu-item owner "Transfer Assets" (routes/transfer-path))
                 [:li.divider {:role "separator"}]
                 (menu-item owner "Sign out"
                            #(participant-service/sign-out))]]]]]))))

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
(ns mktplace.components.portfolio
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [sawtooth.components.core :as component
              :refer [glyph]
              :refer-macros [handle-event when-changed]]
            [sawtooth.ledger.keys :as keys]
            [mktplace.routes :as routes]
            [mktplace.service.asset :as asset-service]
            [mktplace.service.exchange :as exchange-service]
            [mktplace.service.offer :as offer-service]
            [mktplace.service.selection :as selection-svc]
            [mktplace.components.format :as fmt]
            [mktplace.components.offers :refer [offer-table]]
            [mktplace.components.holdings :refer [holding-detail]]
            [mktplace.components.assets :refer [asset-detail]]
            [mktplace.components.exchanges :refer [exchange-table]]))


(defn- holding-row
  [assets selections selectable? holding]
  (if selectable?
    (let [selected? (= holding (get selections :holding))]
      [:a.list-group-item {:key (:id holding)
                           :href "#"
                           :class (if selected? "active")
                           :on-click (handle-event
                                       (selection-svc/select-holding!
                                         (if-not selected? holding nil)))}
       (om/build holding-detail {:assets assets :holding holding})])
    [:div.list-group-item {:key (:id holding)}
     (om/build holding-detail {:assets assets :holding holding})]))

(defn- holding-list
  ([assets holdings selections] (holding-list assets holdings selections true))
  ([assets holdings selections selectable?]
   (html
     [:div#holdings.list-group
      (if (< 0 (count holdings))
        (->> holdings
             (sort-by :count)
             reverse
             (map (partial holding-row assets selections selectable?)))
        [:div.empty-holdings
         (if (and selectable? (not (empty? assets)))
           "Select an Asset to see Holdings"
           "No Holdings")])])))

(defn asset-row [asset-types selections asset]
  (let [selected? (= asset (get selections :asset))]
    (html
     [:a.list-group-item {:key (:id asset)
                          :href="#"
                          :class (if selected? "active")
                          :on-click (handle-event
                                      (selection-svc/select-asset!
                                        (if-not selected? {:asset asset} nil)))}
      (om/build asset-detail {:asset-types asset-types :asset asset})])))

(defn- asset-list
  [asset-types assets selections]
  (html
    [:div#assets.list-group
     (if (empty? assets)
       [:li.empty-assets "No Assets"]
       (->> assets
            (sort-by :name)
            (map (partial asset-row asset-types selections))))]))

(defn- column-header [label create-link-target]
  (html
    [:div.row
     [:div.col-xs-6
      [:h4 label]]
     [:div.col-xs-6
      [:a {:class "btn btn-default btn-xs pull-right header-btn"
           :href create-link-target} (glyph :plus)]]]))

(defn portfolio [{:keys [asset-types assets holdings selections]} _]
  (reify
    om/IDisplayName
    (display-name [_] "Portfolio")

    om/IRender
    (render [_]
      (html
        [:div.row

         [:div.col-xs-6
          (column-header "Assets" (routes/asset-create-path))
          (asset-list asset-types assets selections)]

         [:div.col-xs-6
          (column-header "Holdings" (routes/holding-create-path))
          (holding-list assets holdings selections)]]))))

(defn- make-revoke-control-fn [participant]
  (fn [offer]
    (html
      [:div.offer-controls
       [:a {:href "#":on-click (handle-event
                                 (offer-service/revoke
                                   (keys/get-key-pair)
                                   participant
                                   offer))}
        (glyph :trash)]])))

(defn- load-portfolio-info [app-state]
  (let [participant (:participant app-state)]
    (asset-service/assets)
    (offer-service/owned-offers participant {:limit 5})
    (exchange-service/exchanges participant {:limit 5})))

(defn portfolio-summary
  [data owner]
  (reify
    om/IDisplayName
    (display-name [_] "PortfolioSummary")

    om/IWillMount
    (will-mount [_]
      (load-portfolio-info data))

    om/IWillReceiveProps
    (will-receive-props [_ next-state]
      (when-changed owner next-state [:block]
        (load-portfolio-info next-state)))

    om/IRender
    (render [_]
      (let [{:keys [assets participant view-participant  participants]} data
            participant (or view-participant participant)
            holdings (get participant :holdings)
            offers (get-in data [:offers :data])
            exchanges (get-in data [:exchanges :data])]
        (html
          [:div.container-fluid
           [:h3.page-header "My Wallet"]
           [:div.row
            [:div.col-md-4
             [:div.scroll-area
              [:h4 "Holdings"]
              (holding-list assets holdings nil false)]]
            [:div.col-md-6
             [:div.offer-area
              (om/build offer-table {:offers offers
                                     :participants participants
                                     :assets assets
                                     :title "My Latest Offers"
                                     :control-fn (make-revoke-control-fn participant)})]
             [:div.exchange-area
              (om/build exchange-table {:exchanges exchanges
                                        :participants participants
                                        :assets assets
                                        :title "My Recent Exchanges"})]]]])))))

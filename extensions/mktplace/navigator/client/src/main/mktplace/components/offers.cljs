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
(ns mktplace.components.offers
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [taoensso.timbre :as timbre
             :refer-macros [infof]]
            [goog.string :as gstring]
            [sawtooth.ledger.keys :as keys]
            [sawtooth.router :as router]
            [sawtooth.math :as math]
            [sawtooth.utils :refer [first-by]]
            [sawtooth.components.core
             :refer [glyph paging ->int
                     radio-buttons text-field select-field form-buttons]
             :refer-macros [handle-event when-changed when-new-block handle-submit]]
            [sawtooth.components.notification :refer [notify!]]
            [mktplace.routes :as routes]
            [mktplace.service.participant :as participant]
            [mktplace.service.offer :as offer]
            [mktplace.components.format :as fmt]
            [mktplace.components.participants :refer [participant-link]]
            [mktplace.transactions]))

;
; Offer Table

(defn- pending-label [{:keys [pending revoked processing]}]
  (cond
    pending "Pending"
    revoked "Revoking"
    processing "Processing"))

(defn- offer-display [offer]
  (let [f (math/ratio->fraction (:ratio offer))
        pending? (or (:pending offer) (:revoked offer) (:processing offer))]
    (merge (select-keys offer [:input-name :output-name :creator])
           {:input-amount (math/denominator f)
            :output-amount (math/numerator f)
            :pending? pending?
            :pending-label (pending-label offer)
            :offer-id (:id offer)})))

(defn- with-creator [participants]
  (fn [offer]
    (assoc offer :creator (first-by participants :id (:creator offer)))))

(defn- with-asset-names [assets]
  (fn [offer]
    (assoc offer
           :input-name (fmt/asset-name-by-holding assets (get offer :input))
           :output-name (fmt/asset-name-by-holding assets (get offer :output)))))

(defn- offer-row [control-fn]
  (fn [offer]
    (let [{:keys [input-name input-amount
                  output-name output-amount
                  offer-id creator
                  pending? pending-label]} (offer-display offer)]
      (html
        [:tr {:key offer-id
              :class (if pending? "pending")}
         [:td (participant-link creator)]
         [:td.text-right input-amount]
         [:td input-name]
         [:td.text-right output-amount]
         [:td output-name]
         (cond
            (and control-fn (not pending?)) [:td (control-fn offer)]
            (and control-fn pending?) [:td [:em (glyph :hourglass) (str " " pending-label)]])]))))

(defn offer-table [{:keys [offers participants assets title control-fn]
                    :or {title "Open Offers"}} owner]
  (om/component
    (html
      [:div
       [:h3 title]
       [:table.table
        [:thead
         [:tr
          [:th "Owner"]
          [:th.text-right "#"]
          [:th "Input"]
          [:th.text-right "#"]
          [:th "Output"]
          (if control-fn [:th] nil)]]
        [:tbody
         (if (> (count offers) 0)
           (map
             (comp (offer-row control-fn)
                   (with-asset-names assets)
                   (with-creator participants))
             offers)
           [:tr
            [:td.text-center {:col-span (if control-fn 6 5)} "No Offers"]]
         )]]])))

;
; Offer Page

(defn make-offer-control-fn [owner participant]
  (fn [offer]
    (html
      [:div.offer-controls
       (if (= (get-in offer [:creator :id]) (get participant :id))
         [:a {:href "#" :on-click (handle-event
                                    (offer/revoke (keys/get-key-pair) participant offer))}
          (glyph :trash) " Revoke"]
         [:a {:href "#" :on-click (handle-event
                                    (router/push (routes/exchange-offer-path {:initial-offer-id (:id offer)})))}
          (glyph :transfer) " Accept"])])))


(def ^:const PAGE_SIZE 10)

(defn- load-offers [state page]
  (offer/available-offers (:participant state)
                          {:limit PAGE_SIZE :page page
                           :assetId (get-in state [:selections :asset :id])
                           :holdingId (get-in state [:selections :holding :id])}))

(defn- offer-page-fn [app-state owner]
  (fn [page]
    (load-offers app-state page)
    (om/set-state! owner :page page)))

(defn offers [data owner]
  (reify
    om/IDisplayName
    (display-name [_] "Offers")

    om/IInitState
    (init-state [_]
      {:page 0})

    om/IWillMount
    (will-mount [_]
      (load-offers data (om/get-state owner :page)))

    om/IWillReceiveProps
    (will-receive-props [_ next-state]
      (when-changed owner next-state [:block :selections]
      (load-offers next-state (om/get-state owner :page))))

    om/IRenderState
    (render-state [_ {:keys [page]}]
      (let [{:keys [participant participants assets]} data
            offers (get-in data [:offers :data])
            offer-count (get-in data [:offers :count] 0)]
      (html
        [:div.container-fluid

         [:div.row
          (om/build offer-table {:offers offers
                                 :participants participants
                                 :assets assets
                                 :control-fn (make-offer-control-fn owner participant)})]

         (if (< PAGE_SIZE offer-count)
           [:div.row
            (om/build paging {:current-page page
                              :total-items offer-count
                              :items-per-page PAGE_SIZE
                              :go-to-page-fn (offer-page-fn data owner)})])])))))

;
; Sell Offer Form


(defn- viewable-holdings [app-state]
   (let [get-asset-name (partial fmt/asset-name-by-holding (get app-state :assets))]
       (->> (get-in app-state [:participant :holdings])
          (sort-by :name)
          (map #(assoc % :asset-name (get-asset-name %))))))

(defn- set-initial-form-state [owner app-state initial-form]
  (let [available-assets (viewable-holdings app-state)
        selected-id (-> available-assets first :id)]
    (om/update-state!
      owner
      (constantly (merge initial-form {:input selected-id
                                       :output selected-id})))))

(defn- do-submit [participant sell-offer]
  (offer/submit-offer (keys/get-key-pair) participant sell-offer)
  (router/push (routes/offers-path {:participant-id (get participant :id)})))

(defn- is-valid? [{:keys [input output minimum maximum]}]
  (and (not (nil? input))
       (not (nil? output))
       (not (nil? minimum))
       (not (nil? maximum))
       (not= input output)))

(defn- handle-submit [owner participant sell-offer]
  (handle-event
    (if (is-valid? sell-offer)
      (do-submit participant sell-offer)
      (notify! {:type :warn
                :title "Invalid Sell Offer"
                :message "Input and output must be different holdings!"}))))

(defn sell-offer-form [data owner]
  (let [initial-state {:input-count 1 :output-count 1
                       :execution "Any"
                       :minimum 1
                       :maximum math/max-int}
        reset-form #(set-initial-form-state owner % initial-state)]
    (reify
      om/IDisplayName
      (display-name [_] "SellOfferForm")

      om/IInitState
      (init-state [_] initial-state)

      om/IWillMount
      (will-mount [_]
        (reset-form data))

      om/IWillReceiveProps
      (will-receive-props [_ next-state]
        (when-new-block owner next-state
          (reset-form next-state)))

      om/IRenderState
      (render-state [_ state]
        (let [participant (:participant data)
              holdings (viewable-holdings data)
              holding-options (map (fn [{:keys [id asset-name] :as holding}]
                                    (html [:option {:key id  :value id}
                                           (str (fmt/object-name holding) " (" asset-name ")")]))
                                 holdings)
              submit-handler (handle-submit owner "sell-offer-form"
                               (if (is-valid? state)
                                 (do-submit participant state)
                                 (notify! {:type :warn
                                           :title "Invalid Sell Offer"
                                           :message "Input and output must be different holdings!"})))
              reset-handler (handle-event (reset-form data))]

          (html
            (if-not (empty? holdings)
              [:div.container-fluid
               [:h3 "Create Sell Offer"]

               [:form.sell-offer-form {:on-submit submit-handler
                                       :ref "sell-offer-form"}

                (text-field owner :name "Name"
                            {:help-text "An optional, human-readable name for the sell offer.
                                        Must beging with '/'"})

                (text-field owner :description "Description"
                            {:help-text "Optional information about the sell offer."})

                (select-field owner :input "Input" holding-options
                              {:help-text "The holding into which payment is made"})

                (text-field owner :input-count "Amount" {:type "number"
                                                         :min 1
                                                         :parse-fn ->int})

                (select-field owner :output "Output" holding-options
                              {:help-text "The holding from which assets are transfered"})

                (text-field owner :output-count "Amount" {:type "number"
                                                          :min 1
                                                          :parse-fn ->int})

                (text-field owner :minimum "Minimum"
                            {:help-text "The minimum number of input instances"
                             :required true
                             :type "number"
                             :min 1
                             :parse-fn ->int})

                (text-field owner :maximum "Maximum"
                            {:help-text "The maximum number of input instances"
                             :required true
                             :type "number"
                             :min 1
                             :max math/max-int
                             :parse-fn ->int})

                (radio-buttons owner :execution
                               [["Executeable multiple times" "Any"]
                                ["Executeable once" "ExecuteOnce"]
                                ["Executeable once per participant" "ExecuteOncePerParticipant"]])

                (form-buttons owner initial-state
                              {:submit {:disabled (not (is-valid? state))}})]]

              [:div.container-fluid
               "You have no holdings!"])))))))

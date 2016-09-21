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
(ns mktplace.components.exchanges
  (:require [om.core :as om]
            [goog.string :as gstring]
            [sablono.core :as html :refer-macros [html]]
            [mktplace.service.participant :as participant]
            [mktplace.service.exchange :as exchange-service]
            [mktplace.service.offer :as offer-service]
            [mktplace.service.participant :as participant-service]
            [mktplace.components.format :as fmt]
            [mktplace.routes :as routes]
            [mktplace.transactions :as txns]
            [mktplace.components.holdings :refer [holding-detail]]
            [mktplace.components.participants :refer [participant-link]]
            [sawtooth.ledger.keys :as keys]
            [sawtooth.router :as router]
            [sawtooth.utils :refer [first-by]]
            [sawtooth.components.core
             :refer [paging glyph nbsp classes
                     modal-container modal-scaffold
                     basic-text-field text-field ->int form-buttons
                     dropdown]
             :refer-macros [when-changed handle-event handle-submit]]
            [sawtooth.math :as math]))

(defn- with-participants [participants]
  (fn [exchange]
    (assoc exchange
           :payee (first-by participants :id
                    (get-in exchange [:input :creator]))
           :payer (first-by participants :id
                    (get-in exchange [:sellOffer :creator])))))

(defn- with-asset-names [assets]
  (fn [exchange]
    (assoc exchange
           :input-name (fmt/asset-name-by-holding
                         assets (get exchange :input))
           :output-name (fmt/asset-name-by-holding
                          assets (get exchange :output)))))

(defn- exchange-row
  [{:keys [id input-name output-name payee payer amount] :as txn}]
  (let [f (math/ratio->fraction (get-in txn [:sellOffer :ratio]))]
    (html
      [:tr {:key id
            :class (classes {:danger (:failed txn)
                             :active (:pending txn)})}
       [:td
        [:span.amount (* amount (math/denominator f))] " " [:span.type input-name]
        [:br]
        [:span.participant
         (if payee
           (participant-link payee)
           "Unknown Participant")]]
       [:td.text-center.for-column "for"]
       [:td
        [:span.amount (* amount (math/numerator f))] " " [:span.type output-name]
        [:br]
        [:span.participant
         (if payer
           (participant-link payer)
           "Unknown Participant")]]])))

(defn exchange-table
  [{:keys [exchanges participants assets title]
    :or {title "Historic Exchanges"}} owner]
  (om/component
    (html
      [:div
       [:h3 title]
       [:table.table.exchange-table
        [:tbody
         (if (> (count exchanges) 0)
           (map (comp exchange-row
                      (with-asset-names assets)
                      (with-participants participants))
                exchanges)
           [:tr
            [:td.text-center {:col-span 3} "No Exchanges"]])]]])))

;
; Exchange Form

(defn- holding-by-id [holdings id]
  (first-by holdings :id id))

(defn- match-holdings-by-asset [holdings holding-to-match]
  (filter #(= (:asset holding-to-match) (:asset %)) holdings))

(defn- holdings-to-dropdown-items [holdings]
  (map (fn [{holding-id :id holding-name :name :as holding}]
         {:id holding-id :label holding-name :value holding})
       holdings))

(defn are-modeled-holdings-valid?
  ([participant-holdings state] (are-modeled-holdings-valid? participant-holdings nil state))
  ([participant-holdings offers {:keys [initial-liability final-liability quantity]}]
   (let [initial-holding (holding-by-id participant-holdings initial-liability)
         final-holding (holding-by-id participant-holdings final-liability)
         modeled-holdings (exchange-service/compute-model-holdings
                            offers
                            initial-holding
                            final-holding quantity)]
     (reduce (fn [valid? pair]
               (and valid?
                    (<= 0 (get-in pair [:left :count]))
                    (<= 0 (get-in pair [:right :count]))))
             true
             modeled-holdings))))

(defn- is-valid-exchange?
  [app-state
   {:keys [initial-liability final-liability quantity] :as state}]
  (let [first-offer (first (get-in app-state [:exchange :offers]))]
    (and initial-liability final-liability
         (<= (get first-offer :minimum) quantity (get first-offer :maximum))
         (are-modeled-holdings-valid?
           (get-in app-state [:participant :holdings])
           (get-in app-state [:exchange :offers])
           state)
         (if (= :new-holding final-liability)
           (fmt/valid-object-name? (get-in state [:new-final-holding :name]))
           true))))

(def direction-label {:output "Input" :input "Output"})
(def input-direction-label {:ouput "output" :input "input"})

(defn add-offer-modal
  [{:keys [on-close-fn
           on-select-fn
           direction
           asset-id
           participant
           assets]
    {offers :data offer-count :count} :offers}
   owner]
  (reify
    om/IWillMount
    (will-mount [_]
      (offer-service/exchange-offers-with participant {direction asset-id}))

    om/IWillUnmount
    (will-unmount [_]
      (offer-service/clear-exchange-offers-with))

    om/IRender
    (render [_]
      (modal-scaffold
        on-close-fn
        (html
          [:h3 (gstring/format "Insert an %s Offer" (direction-label direction))])
        (html
          [:div
           [:p "Select an offer."]
            (if (and (not (nil? offers)) (empty? offers))
              [:div (gstring/format "No offers have %s as %s."
                                    (fmt/first-name assets asset-id "unknown")
                                    (-> direction input-direction-label .toLowerCase))]
               [:div.list-group
                (map (fn [o]
                       [:a.list-group-item {:href "#"
                                            :key (:id o)
                                            :on-click (handle-event
                                                        (on-select-fn o)
                                                        (on-close-fn))}
                        (let [{input-amount :denominator output-amount :numerator}
                              (math/ratio->fraction (get o :ratio))]
                          (gstring/format "%s %s for %s %s"
                                          input-amount
                                          (fmt/asset-name-by-holding assets (:input o))
                                          output-amount
                                          (fmt/asset-name-by-holding assets (:output o))))])
                     offers)])])))))

(defn- holding-pair-row
  [participant assets participants {:keys [left right]}]
  (let [participant-id (get participant :id)
        left-creator (get left :creator)
        right-creator (get right :creator)
        left-creator (when (not= left-creator participant-id)
                       (fmt/participant-display-name participants left-creator))
        right-creator (when (not= right-creator participant-id)
                        (fmt/participant-display-name participants right-creator))]
    (html
      [:tr {:key (str (:id left) "-" (:id right))}
       [:td.holding
        (if left
          (om/build holding-detail {:assets assets
                                    :participant-name left-creator
                                    :holding left})
          [:span "No Initial Holding"])]
       [:td nbsp]
       [:td.holding
        (if right
          (om/build holding-detail {:assets assets
                                    :participant-name right-creator
                                    :holding right})
          [:span.pull-right "No Final Holding"])]])))

(defn- modeled-holding-table
  [{:keys [participant assets participants
           offers initial-holding final-holding quantity]} owner]
  (om/component
    (let [{input-amount :denominator}
          (math/ratio->fraction (get (first offers) :ratio))

          modeled-holdings
          (exchange-service/compute-model-holdings
            offers
            initial-holding
            final-holding
            (* input-amount quantity))]
      (html
        [:table.table-basic.exchange-model-table
         [:thead
          [:tr
           [:th "Input"]
           [:td (glyph :arrow-right)]
           [:th.pull-right "Output"]]]
         [:tbody
          ; Offer holdings
          (map (partial holding-pair-row participant assets participants)
               modeled-holdings)]]))))

(defn- holding-field [owner holding]
  (cond
    (:id holding) holding

    (nil? holding) nil

    :default
    {:name (basic-text-field owner [:new-final-holding :name]
                             {:placeholder "Holding Name"
                              :class "input-sm new-holding" })
     :count 0
     :creator (:creator holding)
     :asset (:asset holding)}))

(defn exchange-form
  [{[_ {offer-id :initial-offer-id}] :route
    assets :assets
    participant :participant
    participants :participants
    :as data}
   owner]

  (reify
    om/IInitState
    (init-state [_]
      {:quantity 1})

    om/IWillMount
    (will-mount [_]
      (when (nil? (get-in data [:exchange :offers]))
        (offer-service/exchange-offer participant offer-id)))

    om/IWillUnmount
    (will-unmount [_]
      (offer-service/clear-exchange-offers))

    om/IRenderState
    (render-state [_ {:keys [quantity initial-liability final-liability] :as state}]
      (when-let [exchange-state (get data :exchange)]
        (if-let [first-offer (first (get-in data [:exchange :offers]))]
          (let [quantity (or quantity 0)
                offers (get-in data [:exchange :offers])
                last-offer (last offers)

                participant-id (get participant :id)
                participant-holdings (get participant :holdings)

                offer-input-holding (get first-offer :input)
                offer-output-holding (get last-offer :output)

                input-holding-options
                (-> participant-holdings
                    (match-holdings-by-asset offer-input-holding)
                    (holdings-to-dropdown-items))

                initial-holding (holding-by-id participant-holdings initial-liability)
                final-holding
                (if (= :new-holding final-liability)
                  (get state :new-final-holding)
                  (holding-by-id participant-holdings final-liability))

                output-holding-options
                (-> participant-holdings
                    (match-holdings-by-asset offer-output-holding)
                    (holdings-to-dropdown-items))

                insert-offer-fn
                (fn [offer]
                  (let [insert-offer (get state :insert-offer)
                        is-output? (= :output (:direction insert-offer))]
                    (om/set-state! owner (if is-output? :initial-liability :final-liability) nil)
                    (offer-service/insert-exchange-offer offer is-output?)))

                submit-handler
                (handle-submit owner "exchange-form"
                  (txns/exchange
                    (keys/get-key-pair)
                    participant
                    initial-liability
                    final-holding
                    offers
                    quantity
                    #(router/push
                       (routes/offers-path {:participant-id participant-id}))))

                reset-handler (handle-event
                                (router/push
                                  (routes/offers-path {:participant-id participant-id})))]
          (html
            [:div
             (when-let [insert-offer (:insert-offer state)]
               (modal-container insert-offer
                                add-offer-modal
                                (merge insert-offer
                                  {:participant participant
                                   :assets (get-in data [:assets])
                                   :offers (get-in data [:exchange :insert :offers])
                                   :on-select-fn insert-offer-fn
                                   :on-close-fn #(om/set-state! owner :insert-offer nil)})))

            [:form.exchange-form
             {:role "form" :ref "exchange-form" :on-submit submit-handler}
             [:h4 "Execute Exchange"]

             [:div.row
               [:div.btn-group {:role "group"}
                 (dropdown owner
                           :initial-liability
                           "Initial Holding"
                           input-holding-options
                           {:class "btn-group"
                            :role "group"})
                 [:button.btn.btn-default
                  {:type "button"
                   :on-click (handle-event
                               (let [asset-id (get offer-input-holding :asset)]
                                 (om/set-state! owner
                                                :insert-offer
                                                {:direction :output
                                                 :asset-id asset-id})))}
                  "+ Offer"]
                 (when (< 1 (count offers))
                   [:button.btn.btn-default
                    {:on-click (handle-event
                                 (om/set-state! owner :initial-liability nil)
                                 (offer-service/release-exchange-offer (get first-offer :id)))}
                    "- Offer"])]]

             [:div.row
              (om/build modeled-holding-table (merge (select-keys
                                                       data
                                                       [:participant
                                                        :participants
                                                        :assets])
                                                     {:offers offers
                                                      :initial-holding initial-holding
                                                      :final-holding
                                                      (holding-field owner final-holding)
                                                      :quantity quantity}))]

             [:div.clearfix

             [:div.row.final-holding-ctrls
              [:div.btn-group
               (when  (not= offer-id (get (last offers) :id))
                 [:button.btn.btn-default
                  {:on-click (handle-event
                               (om/set-state! owner :final-liability nil)
                               (offer-service/release-exchange-offer (get last-offer :id)))}
                   "- Offer"])

              [:button.btn.btn-default
               {:on-click (handle-event
                            (om/set-state! owner
                                           :insert-offer
                                           {:direction :input
                                            :asset-id (get offer-output-holding :asset)}))}
               "+ Offer"]
               (dropdown owner
                         :final-liability
                         "Final Output Holding"
                         (concat
                           output-holding-options
                           [:divider
                            {:id :new-holding
                             :label "New Holding"
                             :on-select #(om/set-state! owner :new-final-holding
                                                        {:asset (get offer-output-holding :asset)
                                                         :creator participant-id})}])
                         {:class "btn-group"
                          :role "group"})]]

             [:div.row
              (text-field owner :quantity  "Quantity"
                          {:type "number"
                           :min 1
                           :max (get first-offer :maximum)
                           :parse-fn ->int
                           :help-text (str "Number of executions of "
                                           (if (and (get first-offer :name)
                                                    (< 0 (count (get first-offer :name))))
                                             (get first-offer :name)
                                             "Offer"))})

              (form-buttons owner {}
                            {:submit {:label "Accept"
                                      :disabled (not (is-valid-exchange? data state))}
                             :reset {:label "Cancel"
                                     :on-click reset-handler}})]]]]))
          (html
            [:div.alert.alert-danger "Unknown initial offer"]))))))

;
; Exchange lists

(def ^:const PAGE_SIZE 10)

(defn- load-exchanges [state page]
  (exchange-service/exchanges {:limit PAGE_SIZE :page page
                               :assetId (get-in state [:selections :asset :id])
                               :holdingId (get-in state [:selections :holding :id])}))

(defn- exchange-page-fn [data owner]
  (fn [page]
    (load-exchanges data page)
    (om/set-state! owner :page page)))

(defn exchanges [data owner]
  (reify
    om/IInitState
    (init-state [_]
      {:page 0})

    om/IWillMount
    (will-mount [_]
      (load-exchanges data (om/get-state owner :page)))

    om/IWillUnmount
    (will-unmount [_]
      (exchange-service/clear-exchanges))

    om/IWillReceiveProps
    (will-receive-props [_ next-state]
      (when-changed owner next-state [:block :selections]
        (load-exchanges next-state (om/get-state owner :page))))

    om/IRenderState
    (render-state [_ state]
      (let [exchanges (get-in data [:exchanges :data])
            total (get-in data [:exchanges :count] 0)
            assets (get data :assets)]
      (html
        [:div.container-fluid
         [:div.row
          (om/build exchange-table {:exchanges exchanges
                                    :assets assets
                                    :participants (:participants data)})]
         (if (< PAGE_SIZE total)
           [:div.row
            (om/build paging {:current-page (:page state)
                              :total-items total
                              :items-per-page PAGE_SIZE
                              :go-to-page-fn (exchange-page-fn data owner)})])])))))

;
; Transfer form

(defn- is-valid-transfer?
  [app-state {:keys [initial-liability final-liability quantity] :as state}]
  (and (< 0 quantity)
       initial-liability
       final-liability
       (not= initial-liability final-liability)
       (are-modeled-holdings-valid? (get-in app-state [:participant :holdings])
                                    state)))

(defn- holdings-by-selections
  "Returns the holdings restricted by the selection values."
  [selections holdings]
  (if (get selections :asset)
    (filter #(= (:asset %) (get-in selections [:asset :id]))
            holdings)
    holdings))

(defn- form-row [label field]
  (html
    [:div.row
     [:div.col-xs-2
      [:label label]]
     [:div.col-xs-10 field]]))

(defn transfer-form [data owner]
  (let [initial-state {:quantity 1}]
    (reify

      om/IInitState
      (init-state [_] initial-state)

      om/IRenderState
      (render-state
        [_ {:keys [initial-liability final-liability quantity selected-participant] :as state}]
        (let [{:keys [participant participants selections]} data
              source-holdings (holdings-by-selections
                                selections (get participant :holdings))

              target-holdings (if (nil? selected-participant)
                                source-holdings
                                (if-let [other-holding
                                         (get-in data [:transfer :target-participant :holdings])]
                                  (holdings-by-selections
                                    selections
                                    other-holding)
                                  [{:name "Loading..."}]))

              initial-holding (holding-by-id source-holdings initial-liability)
              final-holding (holding-by-id target-holdings final-liability)

              submit-handler
              (handle-submit owner "transfer-form"
                (txns/exchange
                  (keys/get-key-pair)
                  participant
                  initial-liability
                  final-liability
                  []
                  quantity
                  #(router/push (routes/portfolio-path))))

              cancel-handler
              (handle-event
                (router/push (routes/portfolio-path)))]
        (html
          [:form.form.transfer-form
           {:ref "transfer-form" :on-submit submit-handler}
           [:h3 "Transfer Assets"]
           (form-row "Source"
             (dropdown owner :initial-liability "Select a Holding"
                       (holdings-to-dropdown-items source-holdings)))

           (when initial-liability
             (form-row "Participant"
               (dropdown owner :selected-participant "Self"
                         (map (fn [{participant-id :id participant-name :name}]
                                {:label participant-name :id participant-id})
                              participants)
                         {:on-change #(if-not (nil? %)
                                        (participant-service/transfer-target-participant %)
                                        (participant-service/clear-transfer-target-participant))})))

           (when initial-liability
             (form-row "Destination"
               (dropdown owner :final-liability "Select a holding"
                         (holdings-to-dropdown-items
                           (filter #(and (= (:asset %) (:asset initial-holding))
                                         (not= initial-liability (:id %)))
                                   target-holdings)))))

           (text-field owner :quantity "Amount"
                       {:type "number"
                        :min 1
                        :parse-fn ->int
                        :help-text "The amount to transfer." })

           (when (and initial-holding final-holding)
             [:div.row
              (om/build modeled-holding-table
                        (merge
                          (select-keys data [:participant :participants :assets])
                          {:initial-holding initial-holding
                           :final-holding final-holding
                           :quantity quantity }))])

           (form-buttons owner initial-state
                         {:submit {:label "Transfer"
                                   :disabled (not (is-valid-transfer? data state))}
                          :reset {:label "Cancel"
                                  :on-click cancel-handler}})]))))))

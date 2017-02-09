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
(ns sawtooth.components.block
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [goog.string :as gstring]
            [sawtooth.service.block :as block-service]
            [sawtooth.components.core
             :refer [paging classes modal-container modal-scaffold]
             :refer-macros [when-new-block handle-event]]))


(def ^:const transaction-limit 10)

(defn- load-transactions [page]
  (block-service/transactions {:page page :limit transaction-limit}))

(defn- load-history [page]
  (load-transactions page)
  (block-service/chain-info))

(defn- load-history-page-fn [owner]
  (fn [page]
    (load-transactions page)
    (om/set-state! owner :page page)))

(def status-text ["Unknown" "Pending" "Committed" "Failed"])
(def status-class ["danger" "warning" nil "danger"])

(defn- transaction-row
  [on-row-selected-fn is-selected?
   {txn-id :id txn-type :TransactionType status :Status :as txn}]
  (let [update-type (cond
                      (get-in txn [:Update :UpdateType]) (get-in txn [:Update :UpdateType])
                      (= (count (get txn :Updates)) 1) (get-in txn [:Updates 0 :UpdateType])
                      (get txn :Updates) "Multiple"
                      :default "Unknown")]
    (html
      [:tr {:key txn-id
            :class (classes {:active (is-selected? txn-id)
                             (status-class status) true})
            :on-click (handle-event
                        (on-row-selected-fn txn-id))}
       [:td txn-id]
       [:td txn-type]
       [:td update-type]
       [:td (get status-text status)]])))

(defn- dependency-link [dependency-id]
  (html
    [:a {:key (str "dep" dependency-id)
         :href "#"
         :on-click (handle-event
                     (block-service/transaction-detail dependency-id))}
     dependency-id]))


(defn transaction-detail
  "Renders a given transaction's content, if it is made up of either
  Update or Updates. Anything else is ignored"
  [txn]
  (letfn [(render-update
          ([txn-update] (render-update txn-update name))
          ([txn-update key-fn]
           (->> txn-update
                (remove #(= "" (get % 1)))
                (map #(let [[k v] %]
                        (html
                          [:div {:key (str (key-fn k))}
                           [:dt (name k)]
                           [:dd (str v)]]))))))

          (render-indexed-update
            [i txn-update]
            (html
              [:div {:key i}
               [:br]
               [:dt  "Update"]
               [:dd  (str i)]
               (render-update txn-update #(str (name %) "-" i))]))]
    (html
     [:dl.dl-horizontal.transaction-detail {:key (:id txn)}
      [:dt "InBlock"]
      [:dd (:InBlock txn)]

      [:dt "Dependencies"]
      [:dd (if-not (empty? (:Dependencies txn))
             (interpose ", "
               (map dependency-link (:Dependencies txn)))
             "None")]

      (when (:Update txn)
        [:div
         [:br]
         [:dt "Update"] [:dd ""]
         (render-update (:Update txn))])

      (map-indexed render-indexed-update (:Updates txn))])))

(defn- transaction-detail-modal
  [{txns :transactions} owner]
  (om/component
    (let [txn (first txns)]
      (modal-scaffold #(block-service/clear-transaction-details)
                      (html [:h4 "Transaction " (:id txn)])
                      (html
                        [:div
                         (transaction-detail txn)
                         [:br]
                         [:a {:href "#"
                              :class (when-not (< 1 (count txns)) "invisible")
                              :on-click (handle-event (block-service/pop-transaction-detail))}
                          (gstring/unescapeEntities "&laquo;") " Back"]])
                      true))))

(defn- transaction-detail-row [is-selected? {txn-id :id :as txn}]
  (when (is-selected? txn-id)
    (html
      [:tr {:key (str txn-id "-detail")}
       [:td {:colSpan 4}
        (transaction-detail txn)]])))

(defn history-table
  "Component for a transaction history table. The state provided
  must contain a page number and page function.

  Args:

    state: the Om component state
     :txns - the list of transactions for this page
     :total-txns - the total available transactions
     :page - the current page number (required)
     :page-fn - a function for changing pages (required)
    owner: the Om component owner"
  [{:keys [ txns total-txns page page-fn]} owner]
  (assert (number? page))
  (assert (fn? page-fn))
  (reify

    om/IInitState
    (init-state [_] {})

    om/IRenderState
    (render-state [_ {selected-txn-id :selected}]
      (letfn [#_(on-row-select [txn-id]
                 (om/set-state! owner :selected
                   (if-not (= txn-id selected-txn-id)
                     txn-id
                     nil)))
              (on-row-select [txn-id]
                (block-service/transaction-detail txn-id))

              (is-selected? [txn-id]
                (= txn-id selected-txn-id))]
        (html
          [:div.history-container

           [:div.row
             [:table.table.table-condensed
              [:thead
               [:tr
                [:th "Transaction Id"]
                [:th "Transaction Type"]
                [:th "Update Type"]
                [:th "Transaction Status"]]]

               [:tbody
                (interleave (map (partial transaction-row on-row-select is-selected?) txns)
                            (map (partial transaction-detail-row is-selected?) txns))]]]

           (if (< transaction-limit total-txns)
             [:div.row
              (om/build paging {:current-page page
                                :total-items total-txns
                                :items-per-page transaction-limit
                                :go-to-page-fn page-fn})])])))))

(defn transaction-history
  "Component for displaying the history of the block-chain.

  Args:
    data: the Om component state
    owner: the Om component owner"
  [data owner]
  (reify

    om/IInitState
    (init-state [_] {:page 0})

    om/IWillMount
    (will-mount [_]
      (load-history (om/get-state owner :page)))

    om/IWillUnmount
    (will-unmount [_]
      (block-service/clear-chain-info))

    om/IWillReceiveProps
    (will-receive-props [_ next-state]
      (when-new-block owner next-state
        (load-history (om/get-state owner :page))))

    om/IRenderState
    (render-state [_ {page :page}]
      (html
        (if-let [chain-info (get-in data [:chain :info])]
          [:div.container.transaction-history
           (when-let [transaction-detail-stack (get-in data [:chain :transaction-details])]
             (modal-container (not (empty? transaction-detail-stack))
                              transaction-detail-modal
                              {:transactions transaction-detail-stack}))

           [:h3 "Transaction History"]

           [:div.row
             [:div.panel.panel-default
              [:div.panel-heading
               [:div.panel-title "Current Block"]]
              [:div.panel-body
               [:table.table-basic
                [:thead
                 [:tr
                  [:th "Block Id"]
                  [:th "Block Number"]
                  [:th "Transaction Count"]]]
                [:tbody
                 [:tr
                  [:td (get chain-info :blockid)]
                  [:td (get chain-info :blocknum)]
                  [:td (get chain-info :size)]]]]]]]

           (om/build history-table {:txns (get-in data [:chain :transactions :data])
                                    :total-txns (get-in data [:chain :transactions :count])
                                    :page page
                                    :page-fn (load-history-page-fn owner)})]

          [:div.container "Loading..."])))))

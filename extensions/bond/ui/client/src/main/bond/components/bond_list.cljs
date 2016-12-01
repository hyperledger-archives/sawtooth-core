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

(ns bond.components.bond-list
  (:require [om.core :as om]
            [sablono.core :refer-macros [html]]
            [sawtooth.components.core
             :refer [text-field paging]
             :refer-macros [when-new-block handle-event]]
            [bond.routes :as routes]
            [bond.components.core :as core
             :refer [table heading bond->name bid-ask-pair print-yield format-timestamp]]
            [bond.service.bond :as bond-svc]))

(defn- bond-row
  [{:keys [pending] :as bond}]
  (let [bond-id (:id (core/bond-id bond))
        bond-link (fn [content] [:a {:href (routes/bond-detail {:bond-id bond-id})}
                                content])]
    (let [best-market (core/best-quote bond)]
      [(if-not pending
         (bond-link bond-id)
         bond-id)
       (if-not pending
         (bond-link (bond->name bond))
         (bond->name bond))
       (if best-market
         (bid-ask-pair best-market "price" "/")
         "N/A")
       (if best-market
         (bid-ask-pair best-market "price" "/" #(print-yield % bond))
         "N/A")
       (if best-market
         (format-timestamp (:timestamp best-market) :hour-minute)
         "N/A")
       (if-not pending
         [:a {:href (routes/quote-list {:bond-id bond-id})} "View Quotes"]
         [:span.pending "Pending Commit"])])))

(def ^:const PAGE_SIZE 10)

(defn bond-list [data owner]
  (letfn [(do-load []
            (bond-svc/load-bonds!
              (get-in data [:participant :id])
              {:search (om/get-state owner :search)
               :page (om/get-state owner :page)
               :limit PAGE_SIZE}))
          (go-to-page [page]
            (om/set-state! owner :page page)
            (do-load))]
    (reify

      om/IInitState
      (init-state [_] {:page 0})

      om/IWillMount
      (will-mount [_]
        (do-load))

      om/IWillReceiveProps
      (will-receive-props [_ next-state]
        (when-new-block owner next-state
          (do-load)))

      om/IRender
      (render [_]
        (let [bonds (get-in data [:bonds :data] [])
              total (get-in data [:bonds :count] 0)]
        (html
          [:div.container
           [:h2 "Bonds"]

           [:div.row
            [:form.form-inline.search-form
              (text-field owner :search "Search"
                          {:placeholder "ISIN, CUSIP, or Ticker Symbol"
                           :class "search-input"
                           :parse-fn (fn [s] (when-not (empty? s) s))})

              [:button.btn.btn-primary
               {:on-click (handle-event (do-load))}
               "Go"]
              [:button.btn.btn-default
               {:on-click (handle-event
                            (om/set-state! owner :search nil)
                            (do-load))}
               "Clear"]]]

           [:div.row.bond-table
            (table
              ["ISIN/CUSIP"
               "Bond"
               "Market Prices (Bid/Ask)"
               "Market Yields (Bid/Ask)"
               "Time of Quote"
               ""]
              (map bond-row bonds)
              "No Bonds Found")]

         (if (< PAGE_SIZE total)
           [:div.row
            (om/build paging {:current-page (om/get-state owner :page)
                              :total-items total
                              :items-per-page PAGE_SIZE
                              :go-to-page-fn go-to-page})])]))))))

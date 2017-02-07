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

(ns bond.components.bond-form
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [taoensso.timbre :as timbre
             :refer-macros [debug debugf spy]]
            [sawtooth.state :refer [app-state]]
            [sawtooth.ledger.keys :as keys]
            [sawtooth.router :as router]
            [sawtooth.utils :as utils]
            [sawtooth.components.core
             :refer [text-field radio-buttons select-field form-buttons static-field
                     ->int ->float]
             :refer-macros [handle-event handle-submit]]
            [bond.components.core
             :refer [form-section divided-rows boot-row heading invalid-tip! header-note
                     isin-pattern isin-valid? cusip-pattern cusip-valid?]]
            [bond.transactions :as txns]
            [bond.routes :as routes]))

(def libor-types
  {"Overnight" "Overnight"
   "OneWeek" "1 Week"
   "OneMonth" "1 Month"
   "TwoMonth" "2 Month"
   "ThreeMonth" "3 Month"
   "SixMonth" "6 Month"
   "OneYear" "1 Year"})

(def ^:const FLOATING "Floating")
(def ^:const FIXED "Fixed")

(def ^:const FREQUENCIES ["Quarterly", "Monthly", "Daily"])

(defn is-fixed? [state]
  (not (= (:coupon-type state) FLOATING)))

(defn- parse-date [iso-date]
  (let [date (clojure.string/split iso-date #"-")]
    (clojure.string/join "/" (concat (rest date) [(first date)]))))

(defn- parse-dates [bond]
  (assoc bond
    :first-settlement-date (parse-date (:first-settlement-date bond))
    :maturity-date (parse-date (:maturity-date bond))
    :first-coupon-date (parse-date (:first-coupon-date bond))))

(def float-pattern #"^-?\d*(\.\d+)?$")

(defn has-valid-ids [isin cusip]
  (and (or (not-empty isin) (not-empty cusip))
       (or (empty? isin) (isin-valid? isin))
       (or (empty? cusip) (cusip-valid? cusip))))

(defn is-valid?
  [{:keys [firm isin cusip amount-outstanding coupon-rate coupon-type
           coupon-benchmark maturity-date first-coupon-date]}]
  (and (has-valid-ids isin cusip)
       (not (empty? firm))
       maturity-date
       first-coupon-date
       (and (number? amount-outstanding) (number? (->float coupon-rate)))
       (or (= coupon-type FIXED) (not (nil? coupon-benchmark)))))

(defn org-option [{:keys [id name]}]
  [:option {:key id :value id} name])

(defn- do-submit [participant-id org firms state owner]
  (if (is-valid? state)
    (let [coupon-rate (:coupon-rate state)
          bond (cond-> (dissoc state :firm :outlet-index)
                 true (assoc :coupon-rate (->float coupon-rate))
                 true (parse-dates)
                 (is-fixed? state) (dissoc :coupon-benchmark))]
      (om/set-state! owner :submitted true)
      (txns/create-bond
        (keys/get-key-pair)
        participant-id
        org
        bond
        firms
        #(router/push (routes/bond-list))))
    (invalid-tip! "Create Bond" "Form is invalid. How's your CUSIP/ISIN?")))

(defn bond-form [data owner]
  (let [initial-state {:coupon-type FIXED
                       :coupon-frequency (first FREQUENCIES)}
        owner-field (partial text-field owner)]
    (reify
      om/IInitState
      (init-state [_] initial-state)

      om/IRenderState
      (render-state[_ {:keys [coupon-rate] :as state}]
        (let [{orgs false firms true} (->> (:organizations data)
                                           (group-by #(contains? % :pricing-source)))
              selected-org #(utils/first-by orgs :id (:firm state))]
        (html
          [:div.container
           (heading "Create Bond")
           [:form.form.quote-form
            {:ref "create-bond"
             :on-submit (handle-submit owner "create-bond"
                          (do-submit (get-in data [:participant :id])
                                     (selected-org)
                                     firms
                                     state
                                     owner))}

            (form-section "Issuer" "issuer"
                          (select-field owner :firm "Issuer"
                                        (conj (map org-option orgs)
                                              [[:option "Select an Issuer..."]])
                                        {:required true})
                          (let [org (selected-org)]
                            (divided-rows
                              (static-field "Industry" (get org :industry "None Specified"))
                              (static-field "Ticker" (get org :ticker "None Specified")))))

            (form-section (header-note "Credit Debt Ratings" "optional") "ratings"
                          (boot-row
                            (owner-field [:corporate-debt-ratings :moodys] "Moody's")
                            (owner-field [:corporate-debt-ratings :s-and-p] "S&P")
                            (owner-field [:corporate-debt-ratings :fitch] "Fitch")))

            (form-section (header-note "Identifiers" "enter one") "identifiers"
                          (divided-rows
                            (owner-field :cusip
                                         (header-note
                                           "CUSIP"
                                           "what's this?"
                                           "https://en.wikipedia.org/wiki/CUSIP")
                                         {:required (empty? (:isin state))
                                          :pattern cusip-pattern})
                            (owner-field :isin
                                         (header-note
                                           "ISIN"
                                           "what's this?"
                                           "https://en.wikipedia.org/wiki/International_Securities_Identification_Number")
                                         {:required (empty? (:cusip state))
                                          :pattern isin-pattern})))

            (form-section "Bond Details" "details"
                          (divided-rows
                            (owner-field :first-settlement-date
                                         (header-note "1st Settle Date" "optional")
                                         {:type "date"})

                            (owner-field :maturity-date "Maturity Date"
                                         {:type "date"
                                          :required true}))

                          (owner-field :face-value
                                       (header-note "Face Value" "typically $1000")
                                       {:type "number"
                                        :required true
                                        :min 0
                                        :parse-fn ->int})

                          (owner-field :amount-outstanding
                                       (header-note "Amount Outstanding" "typically 1000000+")
                                       {:type "number"
                                        :required true
                                        :min 0
                                        :parse-fn ->int}))

            (form-section "Coupon Details" "coupon"
                         	[:div [:h5 "Type"]
                          (radio-buttons owner :coupon-type
                             [[FIXED FIXED]
                              [FLOATING FLOATING]]
                             {:inline? true})]

                          (divided-rows
                            (select-field owner :coupon-frequency "Frequency"
                                          (map (fn [value]
                                                 [:option {:key value :value value} value])
                                               FREQUENCIES)
                                          {:required true})
                            (owner-field :first-coupon-date "1st Date"
                                         {:type "date"
                                          :required true})

                            (owner-field :coupon-rate
                                         (header-note
                                           "Rate"
                                           "what's this?"
                                           "https://en.wikipedia.org/wiki/Coupon_(bond)")
                                         {:status (if-not (or (nil? coupon-rate) (->float coupon-rate)) :error)
                                          :required true })
                            (select-field owner :coupon-benchmark "Benchmark"
                                          (->
                                          (map (fn [[value label]]
                                                 [:option {:key value :value value}
                                                  (str "LIBOR "label " USD")])
                                               libor-types)
                                          (conj [:option {:key 0} "Select a LIBOR Benchmark..."]))
                                         {:disabled (is-fixed? state)
                                          :required (not (is-fixed? state))})))

           (form-buttons owner initial-state
                         {:submit {:label "Create Bond"
                                   :disabled (:submitted state)}})]]))))))

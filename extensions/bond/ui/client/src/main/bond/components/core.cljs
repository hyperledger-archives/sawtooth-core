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

(ns bond.components.core
  (:require [om.core :as om]
            [clojure.string :refer [replace split join]]
            [goog.string :as gstring]
            [cljs-time.coerce :as time-coerce]
            [cljs-time.format :as time-format]
            [cljs.pprint :refer [cl-format]]
            [sablono.core :as html :refer-macros [html]]
            [taoensso.timbre :as timbre
             :refer-macros [spy]]
            [sawtooth.math :as math]
            [sawtooth.components.core :refer [->num ->frac]]
            [sawtooth.components.tooltip :refer [timed-tip!]]))

;; VALUES ;;

(defn participant-firm
  [{:keys [organizations participant]}]
  (->> organizations
       (filter #(= (:id %) (:firm-id participant)))
       first))


;;  NUMBERS  ;;

(def isin-pattern #"^[A-Z]{2}[A-Z0-9]{9}[0-9]{1}$")

(def cusip-pattern #"^[0-9]{3}[a-zA-Z0-9]{2}[a-zA-Z0-9*@#]{3}[0-9]$")

(def price-pattern #"^[0-9]{1,3}(-([0-9]|([0-2][0-9]|30|31|32))(\+|( (([1,3]/4)|([1,3,5,7]/8))))?)?$")


(defn- luhn
  "Runs Luhn's alorithm on a number string"
  [s]
  (let [val-str (fn [ch] (if (re-matches #"[0-9]" ch) ch
                    (str (- (.charCodeAt ch 0) 55))))
        double-odds (fn [i n] (* (->num n) (- 2 (mod (+ i 1) 2))))
        sum-digits (fn [sum n] (if (> n 9) (+ sum n -9) (+ sum n)))]
    (-> (->> (map val-str s)
             (join)
             (reverse)
             (map-indexed double-odds)
             (reduce sum-digits))
        (mod 10))))

(defn isin-valid?
  "Validates an isin string"
  [isin]
  (and (not (nil? (re-matches isin-pattern isin)))
       (= 0 (luhn isin))))

(defn cusip-valid?
  [cusip]
  (letfn [(ordinal [c]
            (- (.charCodeAt c 0) 64))

          (c-val [c]
            (cond
              (gstring/isNumeric c) (js/parseInt c)
              (gstring/isAlpha c) (+ (ordinal c) 9)
              (= c \*) 36
              (= c \@) 37
              (= c \#) 38))

          (mod10 [v]
            (mod v 10))]
    (and (not (nil? (re-matches cusip-pattern cusip)))
         (= (js/parseInt (last cusip))
            (->> (butlast cusip)
                 (map c-val)
                 (map-indexed (fn [i v] (if (even? (inc i)) (* v 2) v)))
                 (reduce (fn [sum v]
                           (+ sum
                              (int (/ v 10))
                              (mod v 10)))
                         0)
                 mod10
                 (- 10)
                 mod10)))))

(defn price->perc-of-par
  "Converts a '100-1 1/8+' style bond price string to a decimal number"
  [price]
  (let [price (replace price "+" " 1/2")
        [base tick] (map ->num (split price #"-"))]
    (+ base (/ tick 32))))


(defn price->yield
  "Calculates a bond yield from a '100-1 1/8+' style price string and coupon rate"
  [price coupon]
  (* (/ (->num coupon) (price->perc-of-par price)) 100))

(defn yield->price
  [yield coupon]
  (let [rate (->num coupon)]
    (if (zero? rate)
      (/ 100 (+ yield 1))
      (/ (* 100 rate) yield))))

;;  FORMATTING  ;;

(defn format-price [price]
  (let [base (math/floor price)
        tick (- price base)
        fracional-tick (->frac (* tick 32))
        fracional-tick (replace fracional-tick " 1/2" "+")]
    (if (zero? tick)
      (str base)
      (str base "-" fracional-tick))))

(defn- format-currency
  ([n] (format-currency n "USD"))
  ([n currency]
   (.toLocaleString n "en-US" #js {:style "currency" :currency currency})))

(defn print-yield [price {coupon :coupon-rate}]
  (cl-format nil "~,3f" (price->yield price coupon)))

(defn bond->name
  "Creates a name string for a bond"
  [{issuer :issuer coup :coupon-rate mat :maturity-date}]
  (str issuer " "
       (->frac (->num coup)) " "
       (subs mat 0 (- (count mat) 4)) (subs mat (- (count mat) 2)) " "
       (if (= issuer "T") "Govt" "Corp")))

(defn bond-id
  "Returns either ISIN or CUSIP"
  [{:keys [isin cusip]}]
  (if (and isin (not (empty? isin)))
    {:id isin :key :isin :label "ISIN"}
    {:id cusip :key :cusip :label "CUSIP"}))

(defn format-timestamp
  ([timestamp] (format-timestamp timestamp "M/dd/yyyy HH:mm:ss"))
  ([timestamp format]
   (let [date (time-coerce/from-long (math/floor (* timestamp 1000)))
         fmt (if (keyword? format)
               (time-format/formatters format)
               (time-format/formatter format))]
     (time-format/unparse fmt date))))

(defn sort-quotes [quotes]
  (let [sort-fn #(* -1 (price->perc-of-par (:bid-price %)))]
    (sort-by sort-fn quotes)))

(defn best-quote
  "Given a bond with best-bid and best-ask, it returns an
  amalgamated best quote. If neither exist, it returns nil"
  [{:keys [best-bid best-ask]}]
  (if (and best-bid best-ask)
    {:bid-price (:bid-price best-bid)
     :bid-qty (:bid-qty best-bid)
     :bid-time (:timestamp best-bid)
     :ask-price (:ask-price best-ask)
     :ask-qty (:ask-qty best-ask)
     :ask-time (:timestamp best-ask)
     :timestamp (max (:timestamp best-bid)
                     (:timestamp best-ask))}))

(defn trading-firm? [org]
  (and (:pricing-source org)
       ; The following are orgs created for testing purposes
       (or (not= (first (:pricing-source org)) \z)
           (not= (first (:pricing-source org)) \Z))))


;;  DOM ELEMENTS  ;;

(def ^{:const true :private true} bootstrap-cols 12)

; An OS specific instructional message for copying
(def copy-fail-msg
  (cond (re-find #"iPhone|iPad" (.-userAgent js/navigator))
        "Copying unsupported on iOS"
        (re-find #"Mac" (.-userAgent js/navigator))
        "Press ⌘-C to Copy"
        :default
        "Press Ctrl-C to Copy"))

(defn heading [label & items]
  (into [:div.heading [:h1 label]] items))

(defn header-note
  ([label note] (header-note label note nil))
  ([label note url]
  [label " "
   [:em [:small "("
    (if url
      [:a {:href url :target "_blank"} note]
      note)
    ")"]]]))

(defn form-section
  "Creates sablono-ready code for a form section"
  [heading class-name & rows]
  (into
    [:div {:class class-name}
     [:hr]
     [:h4.form-section heading]]
    rows))

(defn bid-ask-pair
  ([q k sep] (bid-ask-pair q k sep identity))
  ([q k sep convert]
   (str (convert ((keyword (str "bid-" k)) q))
        " " sep " "
        (convert ((keyword (str "ask-" k)) q)))))

(defn- keyed-tags
  "Builds a set of tags with a react key and optional class"
  ([tag items] (keyed-tags tag "" items))
  ([tag class-name items]
   (map-indexed (fn [i item] [tag {:key i :class class-name} item] ) items)))

(defn table
  ([headers rows] (table headers rows nil))
  ([headers rows on-empty]
   [:table.table.table-striped
    [:thead
     [:tr (keyed-tags :th headers)]]
    [:tbody
     (if-not (empty? rows)
       (keyed-tags :tr (map #(keyed-tags :td %) rows))
       [:tr [:td.text-center {:colSpan (count headers)} on-empty]])]]))

(defn n-col-rows
  "Distributes items into n bootstap columns, one item per column per row"
  [n class-name & items]
  (if (not (string? class-name))
    (apply n-col-rows n "" class-name items)
    (let [size (if (> n bootstrap-cols) 1 (int (/ bootstrap-cols n)))
          rows (partition n items)]
      (keyed-tags :div (str "row " class-name)
                  (map #(keyed-tags :div (str "col-sm-" size) %) rows)))))

(defn boot-row
  "Creates a single bootstrap row with as many columns as items"
  [class-name & items]
  (if (not (string? class-name))
    (apply boot-row "" class-name items)
    (apply n-col-rows (count items) class-name items)))

(defn divided-rows
  "Sorts items into rows of two col-sm-6 columns"
  [class-name & items]
  (apply n-col-rows 2 class-name items))

(defn info-item
  "Creates a simple labeled info item from state data"
  ([data key-nest label] (info-item data key-nest label "N/A" identity))
  ([data key-nest label if-nil-or-xform]
   (if (string? if-nil-or-xform)
     (info-item data key-nest label if-nil-or-xform identity)
     (info-item data key-nest label "N/A" if-nil-or-xform)))
  ([data key-nest label if-nil xform]
   [:div
    [:h5 (str label " ")]
    (let [item (get-in data key-nest)]
      (if (nil? item) if-nil (xform item)))]))

(defn link-button
  "Creates a button linking to a URL"
  ([href label] (link-button href label nil))
  ([href label {:keys [btn-type] :as opts}]
   [:a.btn (merge {:class (str "btn-" (name (or btn-type :primary)) " " (if (:class opts) (:class opts)))
                   :href href}
                  (dissoc opts :btn-type :class))
    label]))

(defn description
  ([kvs]
   [:dl.dl-horizontal
    (map-indexed
      (fn [i [k v]]
        [[:dt {:key (str "dt" i)} (name k)]
         [:dd {:key (str "dd" i)} (str v)]])
      kvs)]))

(defn description-entry
  ([label object k] (description-entry label object k identity))
  ([label object k xform]
   (let [v (get-in object (if (vector? k) k [k]))]
     [label (if v (xform v) "N/A")])))

(defn invalid-tip!
  "Uses tooltips to send an invalid form message to the user"
  ([button] (invalid-tip! button "Form Invalid"))
  ([button msg]
   (timed-tip!
    (.querySelector js/document (str "button[label=\"" button "\"]"))
    msg
    5000)))

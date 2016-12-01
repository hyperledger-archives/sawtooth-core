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

(ns sawtooth.components.core
  (:require [om.core :as om]
            [clojure.string :refer [join]]
            [sablono.core :as html :refer-macros [html]]
            [goog.string :as gstring]
            [taoensso.timbre :as timbre
             :refer-macros [debug]]
            [sawtooth.router :as router]
            [sawtooth.math :refer [ceil floor]]
            [sawtooth.events :refer [trigger-event!]]
            [sawtooth.files :refer [upload->string]]
            [sawtooth.service.block :as block])
  (:require-macros [sawtooth.components.core
                    :refer [handler handle-event when-new-block]]))


(defn glyph [k]
  (html [:i {:class (str "glyphicon glyphicon-" (name k))}]))

(defn classes
  "Converts a map to a string of CSS class names All keys in the map
  with logically true values are added to the resulting CSS class string.

  E.g.

  => (classes {:active true :success 1})
    \"active success\""
  [m]
  (when m
    (->> m
         (remove #(or (not (get % 0)) (not (get % 1)))) ; remove logical false values
         (map #(name (get % 0)))
         (join " "))))

(def nbsp (gstring/unescapeEntities "&nbsp;"))
;
; CSS Transitions

(def ^:private react-css-transition-group (.. js/React -addons -CSSTransitionGroup))

(defn create-element [element-type props & more]
  (apply (.-createElement js/React) element-type props more))


(defn css-transition-group [{:keys [component
                                    transition-name
                                    transition-enter-timeout
                                    transition-leave-timeout]} & elements]
  (apply create-element
         react-css-transition-group
         #js {:component (or component "div")
              :transitionName transition-name
              :transitionEnterTimeout transition-enter-timeout
              :transitionLeaveTimeout transition-leave-timeout}
         elements))

;
; Modals

(defn modal-scaffold
  ([close-fn header body] (modal-scaffold close-fn header body false))
  ([close-fn header body background?]
   (let [escape-handler #(when (= (.-key %) "Escape")
                           (.preventDefault %)
                           (close-fn))]
     (html
       [:div

        (when background?
          [:div.modal-bg {:tab-index "1"
                          :on-click (handle-event (close-fn))
                          :on-key-down escape-handler}])

        [:div.modal.animated-modal {:role "dialog"
                                    :tab-index "1"
                                    :on-key-down escape-handler}
         [:div.modal-dialog
          [:div.modal-content
           [:div.modal-header
            [:button {:type "button" :class "close"
                      :aria-label "Close"
                      :on-click (handle-event (close-fn))}
             [:span {:aria-hidden "true"} (gstring/unescapeEntities "&times;")]]
            header]

           [:div.modal-body
            body]]]]]))))

(defn modal-container [display? modal data]
  (css-transition-group {:transition-name "modal"
                         :transition-enter-timeout 500
                         :transition-leave-timeout 300}
                        (if display?
                          (om/build modal data))))

;
; Paging Controls


(defn- has-next? [current-page total-items items-per-page]
  (< current-page (- (ceil (/ total-items items-per-page)) 1)))

(defn- go-back [current-page go-to-page-fn]
  (handle-event
    (when (> current-page 0)
      (go-to-page-fn (dec current-page)))))

(defn- go-next [current-page total-items items-per-page go-to-page-fn]
  (handle-event
    (when (has-next? current-page total-items items-per-page)
      (go-to-page-fn (inc current-page)))))

; Page calculation borrored liberally from
; https://github.com/michaelbromley/angularUtils/tree/master/src/directives/pagination
(defn- calculate-page-number
  "Calculation of a page number with the total pages and with the given
  max-viewable-pages, when on a particular page."
  [i current-page max-viewable-pages total-pages]
  (let [halfway (ceil (/ max-viewable-pages 2))]
    (cond
      (= i max-viewable-pages)
      total-pages

      (= i 0)
      i

      (< max-viewable-pages total-pages)
      (cond
        (< (- total-pages halfway) current-page)
        (+ (- total-pages max-viewable-pages) i)

        (< halfway current-page)
        (+ (- current-page halfway) i)

        :defualt
        i)
      :default
      i)))

(defn make-page-numbers
  "Computes a vector of pages numbers of length max-viewable-pages, where
  gaps in the page numbers are denoted by :..."
  [num-pages current-page max-viewable-pages]
  (let [halfway (ceil (/ max-viewable-pages 2))
        position (cond
                   (<= current-page halfway) :start
                   (< (- num-pages halfway) current-page) :end
                   :default :middle)
        ellipses-needed? (< max-viewable-pages num-pages)]
    (loop [pages (transient [])
           i 0]
      (let [page-number (calculate-page-number i current-page max-viewable-pages num-pages)
            page-number (if (and ellipses-needed?
                                 (or (and (= i 1)
                                          (or (= position :middle) (= position :end)))
                                     (and (= i (- max-viewable-pages 1))
                                          (or (= position :middle) (= position :start)))))
                          :...
                          page-number)]
        (if (and (< i num-pages) (< i max-viewable-pages))
          (recur (conj! pages page-number) (inc i))
          (persistent! (if (= :... (get pages (dec i)))
                         (conj! pages (dec num-pages))
                         pages)))))))

(defn paging
  "Component for for navigating pages of items."
  [{:keys [current-page total-items items-per-page go-to-page-fn max-page-numbers]} owner]
  (reify
    om/IDisplayName
    (display-name [_] "Pager")

    om/IRender
    (render [_]
      (html
        [:nav
         [:ul.pagination
          [:li {:class (if (<= current-page 0) "disabled" "")}
           [:a {:href "#"
                :aria-label "Previous"
                :on-click (go-back current-page go-to-page-fn)}
            [:span {:aria-hidden true} (gstring/unescapeEntities "&lt;")]]]
          ; page numbers
          (let [page-numbers (make-page-numbers (ceil (/ total-items items-per-page))
                                                current-page
                                                (or max-page-numbers 7))]
            (map-indexed
              (fn [i n]
                [:li {:key i
                      :class (if (= n current-page) "active" "")}
                 (if-not (= n :...)
                   [:a {:href "#"
                        :on-click (handle-event
                                    (go-to-page-fn n))}
                    (inc n)]
                   [:a {:href "#"
                        :on-click (handle-event
                                    (go-to-page-fn
                                      (-> (get page-numbers (inc i))
                                          (- (get page-numbers (dec i)))
                                          (/ 2)
                                          floor
                                          (+ (get page-numbers (dec i))))))}
                    "..."])])
              page-numbers))

          [:li {:class (if-not (has-next? current-page total-items items-per-page) "disabled" "")}
           [:a {:href "#"
                :aria-label "Next"
                :on-click (go-next current-page total-items items-per-page go-to-page-fn)}
            [:span {:aria-hidden true} (gstring/unescapeEntities "&gt;")]]]]]))))

;
; Form utils

(defn handle-change
  ([owner k] (handle-change owner k identity nil))
  ([owner k parse-fn post-change-fn]
  (handler [e]
    (let [old-value (om/get-state owner k)
          new-value (parse-fn (.. e -target -value))]
      (om/set-state! owner k new-value)
      (when (and post-change-fn (not= old-value new-value))
        (post-change-fn old-value new-value))))))


;
; Form parts

(defn- field-name
  [k]
  (if (coll? k)
    (clojure.string/join (map name k) ".")
    (name k)))

(defn- form-group [opts & content]
  (html
    (->
      (apply conj
             [:div.form-group {:class (when (:status opts)
                                        (str "has-" (-> opts :status name)))}]
             content)
      (conj
       (when-let [help-text (:help-text opts)]
         [:span.help-block help-text])))))

(defn- form-field-props
  [owner k custom opts]
  (merge {:name (field-name k)
          :value (om/get-state owner k)
          :disabled (:disabled opts)}
         custom
         opts))

(defn- form-field-label [k label]
  (html
    [:label {:for (field-name k)} label]))

(defn- pattern->str [p]
  (if (and p (instance? js/RegExp p))
    (.-source p)
    p))

(defn basic-text-field
  ([owner k] (basic-text-field owner k nil))
  ([owner k opts]
   (let [props (form-field-props
                 owner k
                 {:on-change (handle-change owner k
                                            (get opts :parse-fn identity)
                                            (get opts :did-change-fn))
                  :pattern (pattern->str (get opts :pattern))
                  :type "text"}
                 (dissoc opts :parse-fn :pattern))]
     (html [:input.form-control props]))))

(defn text-field
  ([owner k label] (text-field owner k label nil))
  ([owner k label opts]
   (form-group
     opts
     (html
       [:div
        (form-field-label k label)
        (basic-text-field owner k opts)]))))

(defn static-field
  ([label value] (static-field label value nil))
  ([label value opts]
   (form-group
     opts
     (form-field-label :static label)
     (html [:p.form-control-static value]))))

(defn computed-field
  ([label value] (computed-field label value nil))
  ([label value opts]
   (form-group
     opts
     (form-field-label :computed label)
     (html [:input.form-control (merge {:disabled true :value value} opts)]))))

(defn select-field
  ([owner k label options] (select-field owner k label options nil))
  ([owner k label options opts]
   (let [props (form-field-props owner k
                 {:on-change (handle-change owner k
                                            (get opts :parse-fn identity)
                                            (get opts :did-change-fn))}
                 opts)
         select-ctrl (html [:select.form-control props options])]
     (form-group opts
       (html
         [:div
          (form-field-label k label)
          (if-let [peer (:peer opts)]
            [:div.row
             [:div {:class (when (:peer opts)
                             "col-xs-8")}
              select-ctrl]
             [:div.col-xs-4 peer]]
            select-ctrl)])))))

(defn check-box-field
  ([owner k label] (check-box-field owner k label nil))
  ([owner k label opts]
   (let [props (form-field-props owner k
                 {:type "checkbox"
                  :checked (om/get-state owner k)
                  :on-click (handle-event
                              (om/set-state! owner k (not (om/get-state owner k))))}
                 opts)]
     (form-group opts
       (html
         [:div.checkbox {:class (when (:disabled opts) "disabled")}
          [:label
           [:input props]
           label]])))))

(defn radio-buttons
  ([owner k radio-options] (radio-buttons owner k radio-options nil))
  ([owner k radio-options opts]
   (form-group opts
     (html
       (for [[label value] radio-options]
         (let [props (form-field-props owner k
                       {:type "radio"
                        :on-change (handle-change owner k
                                                  (get opts :parse-fn identity)
                                                  (get opts :did-change-fn))
                        :checked (= (om/get-state owner k) value)
                        :value value}
                       opts)]
           [:div {:key value
                  :class (if (get opts :inline?) "radio-inline" "radio")}
            [:label
             [:input props]
             label]]))))))

(defn form-buttons
  ([owner initial-state] (form-buttons owner initial-state nil))
  ([owner initial-state opts]
   (html
    [:div.form-button-group
     [:button.btn.btn-primary (:submit opts) (get-in opts [:submit :label] "Submit")]
     [:button.btn.btn-default (merge {:type "button"
                                      :on-click (handle-event
                                                  (om/set-state! owner initial-state)
                                                  (when-let [form-ref (get-in opts [:reset :form-ref])]
                                                    (-> (om/get-node owner form-ref)
                                                        (.reset))))}
                                     (:reset opts))
      (get-in opts [:reset :label] "Reset")]])))

(defn upload-text-button
  "Styled button that triggers HTML5 file upload, saves text to the owner's
  state."
  ([owner k label] (upload-text-button owner k label nil))
  ([owner k label opts]
   (let [u-ref (str (name k) "-uploader")
         u-trigger!  (handle-event
                       (trigger-event! (om/get-node owner u-ref) "click"))
         set-text! #(upload->string % (partial om/set-state! owner k))]
     (html
       [:div
        [:input.hidden {:type "file" :ref u-ref :on-change set-text!}]
        [:button.btn.btn-primary (merge {:type "button"
                                         :on-click u-trigger!}
                                    opts) label]]))))

(defn dropdown
  ([owner k label menu-items] (dropdown owner k label menu-items nil))
  ([owner k label menu-items opts]
   (let [selected (om/get-state owner k)
         toggle-key (keyword (str "-" (name k) "-dropdoown"))
         close-fn #(om/set-state! owner toggle-key false)
         is-open? (om/get-state owner toggle-key)
         on-change-fn (get opts :on-change identity)
         select-fn (fn [v on-select-fn]
                     (handle-event
                       (on-change-fn v)
                       (om/set-state! owner k v)
                       (when on-select-fn
                         (on-select-fn))
                       (close-fn)))]
     (html
       [:div.dropdown (merge {:class (classes {:clearfix is-open?
                                               :open is-open?
                                               (:class opts) (:class opts)})}
                             (dissoc opts :class :on-change))
        [:button.btn.btn-default.dropdown-toggle
         {:type "button"
          :id (name toggle-key)
          :on-click (handle-event
                      (om/set-state! owner toggle-key (not is-open?)))}
         (if selected
           (->> menu-items
                (filter #(= selected (:id %)))
                first
                :label)
           label)
         [:span.caret]]
        [:ul.dropdown-menu
         [:li [:a {:href "#"
                   :on-click (select-fn nil identity)}
               label]]
         (map-indexed
           (fn [i {description :label menu-item-id :id on-select-fn :on-select :as item}]
             (if-not (or (= item :divider)
                         (= menu-item-id :divider))
               [:li {:key i}
                [:a {:href "#"
                     :on-click (select-fn menu-item-id on-select-fn)}
                 description]]
               [:li.divider {:key i
                             :role "separator"}]))
           menu-items)]]))))


;
; Generic widgets
(defn link-button
  "Creates a button linking to a URL"
  ([href label] (link-button href label nil))
  ([href label {:keys [btn-type] :as opts}]
   [:a.btn (merge {:class (str "btn-" (name (or btn-type :primary)) " " (if (:class opts) (:class opts)))
                   :href href}
                  (dissoc opts :btn-type :class))
    label]))

(def ^{:const true :private true} bootstrap-cols 12)

(defn- keyed-tags
  "Builds a set of tags with a react key and optional class"
  ([tag items] (keyed-tags tag "" items))
  ([tag class-name items]
   (map-indexed (fn [i item] [tag {:key i :class class-name} item] ) items)))

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

; conversions

(defn ->int
  ([s] (->int s nil))
  ([s default-value]
   (if s
     (try
       (let [i (js/parseInt s 10)]
         (if-not (js/isNaN i)
           i
           default-value))
       (catch :default e
         default-value))
     default-value)))

(defn ->boolean
  ([s] (->boolean s false))
  ([s default-value]
   (if s
     (= (.toLowerCase s) "true")
     default-value)))

(defn ->float
  ([s] (->float s nil))
  ([s default-value]
   (if (and s (not= (last s) \.))
     (try
       (let [n (gstring/toNumber s)]
         (if-not (and (number? n) (js/isNaN n))
           n
           default-value))
       (catch :default e
         default-value))
     default-value)))

(defn ->num
  "Versatile string to number converter that can handle compound fractions"
  ([s] (->num s nil))
  ([s default-value]
   (cond (number? s) s

         (not (string? s)) default-value

         (= (first s) "-") (* -1 (->num (subs s 1)))

         (re-find #" " s)
         (let [nums (map ->num (clojure.string/split s #" "))]
           (reduce + nums))

         (re-find #"/" s)
         (let [fraction (clojure.string/split s #"/")]
           (if (= (count fraction) 2)
             (/ (->num (first fraction)) (->num (last fraction)))
             default-value))

         :else
         (let [num (js/Number s)]
           (if (js/isNaN num) default-value num)))))

(defn ->frac
  "Converts a number to a fraction string with a specified denominator.
  Rounds down any remainder, and reduces as needed."
  ([n] (->frac n 8))
  ([n denom]
   (if (< n 0)
     (str "-" (->frac (* -1 n) denom))
     (let [numer (.floor js/Math (* n denom))
           gcd (loop [x numer y denom] (if (zero? y) x (recur y (mod x y))))
           numer (/ numer gcd)
           denom (/ denom gcd)]
       (cond (= denom 1)
             (str numer)

             (> numer denom)
             (str (.floor js/Math (/ numer denom)) " " (mod numer denom) "/" denom)

             :else
             (str numer "/" denom))))))

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

(ns bond.components.holding-list
  (:require [om.core :as om]
            [sablono.core :refer-macros [html]]
            [cljs.pprint :refer [cl-format]]
            [sawtooth.math :as math]
            [bond.components.page-container :refer [page-container]]
            [bond.components.core
             :refer [table heading bond->name format-currency]]
            [bond.service.holding :refer [load-holdings! clear-holdings!]]))

(defmulti holding-row :asset-type)


(defmethod holding-row "Bond" [{:keys [asset amount]}]
  [(bond->name asset)
   (cl-format nil "~:d" amount)])

(defmethod holding-row "Currency" [{:keys [asset-id amount]}]
  [asset-id
   (format-currency amount asset-id)])

(defmethod holding-row :default [holding]
  [(:asset-type holding)
   (:amount holding)])

(defn- holding-table [data owner]
  (om/component
    (let [holdings (:rows data)]
      (html
        [:div.holding-table
         (table
           ["Asset"
            "Amount" ]
           (map holding-row holdings)
           "No Holdings found")]))))

(defn holdings-list
  [data owner]
  (om/component
    (om/build page-container data
              {:opts {:load-fn (fn [page limit]
                                 (load-holdings! (get-in data [:participant :firm-id])
                                                 {:page page :limit limit}))
                      :unload-fn clear-holdings!
                      :base-path :holdings
                      :table-component holding-table}})))

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

(ns bond.components.page-container
  (:require [om.core :as om]
            [sablono.core :refer-macros [html]]
            [sawtooth.components.core
             :refer [paging]
             :refer-macros [when-new-block]]))

(def ^:const DEFAULT_PAGE_SIZE 10)

(defn xform-data [data additional]
  (reduce (fn [m [k path]]
            (assoc m k (get-in data path)))
          {}
          additional))

(defn page-container [data owner {:keys [load-fn unload-fn page-size table-component
                                         base-path additional-keys]
                                  :or {page-size DEFAULT_PAGE_SIZE}}]
  {:pre [load-fn table-component (or (keyword? base-path) (vector? base-path))]}
  (letfn [(do-load []
            (load-fn (om/get-state owner :page) page-size))
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

      om/IWillUnmount
      (will-unmount [_]
        (when unload-fn
          (unload-fn)))

      om/IRender
      (render [_]
        (let [total (get-in data [base-path :count])]
          (html
            [:div
             (om/build table-component
                       (merge
                         {:rows (get-in data (if (vector? base-path)
                                               (conj base-path :data)
                                               [base-path :data]))}
                         (xform-data data additional-keys)))
             (when (< page-size total)
               [:div
                (om/build paging {:current-page (om/get-state owner :page)
                                  :total-items total
                                  :items-per-page page-size
                                  :go-to-page-fn go-to-page })])]))))))

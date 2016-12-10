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

(ns bond.service.bond
  (:require [sawtooth.service.common :as svc]))


(def ^:const API_URL "/api/bond/bonds")


(defn load-bonds!
  ([participant-id] (load-bonds! nil))
  ([participant-id query]
   (svc/fetch-json!
     API_URL
     (select-keys query [:search :page :limit])
     {:path [:bonds]
      :headers {:participant-id participant-id}
      :on-error {:title "Unable to load bonds"
                 :message "Unable to load bonds due to an unknown
                          server error.  Try again later" }})))

(defn clear-bonds!
  []
  (svc/clear-path! [:bonds]))

(defn load-bond!
  [bond-id]
  (svc/fetch-json!
    (str API_URL "/" bond-id)
    {:path [:bond]
     :on-error {:title "Unable to Load Bond"
                :message (str "Unable to load bond " bond-id
                              " due to an unknown server error. Try
                              again later")}}))

(defn clear-bond!
  []
  (svc/clear-path! [:bond]))

(defn load-bond-identifiers!
  []
   (svc/fetch-json!
     "/api/bond/bond-identifiers"
     {:path [:bond-identifiers]
      :on-error {:title "Unable to load bond ids"
                 :message "Unable to load bonds due to an unknown
                          server error.  Try again later" }}))

(defn clear-bond-identifiers!
  []
  (svc/clear-path! [:bond-identifiers]))

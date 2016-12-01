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

(ns bond.service.order
  (:require [sawtooth.service.common :as svc]))

(def ^:const API_URI "/api/bond/orders")

(defn orders!
  "Fetches orders from the server"
  ([participant-id] (orders! participant-id nil))
  ([participant-id opts]
  (svc/fetch-json!
    API_URI
    (select-keys opts [:page :limit :creator-only :check-pending])
    {:headers {:participant-id participant-id}
     :path [:orders]
     :on-error {:title "Unable to Load Orders"
                :message "An unknown error occured while attempting
                         to fetch orders." }})))

(defn clear-orders!
  "Clears the set of orders out of the app state"
  []
  (svc/clear-path! [:orders]))

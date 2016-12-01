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

(ns bond.service.holding
  (:require [sawtooth.service.common :as service]
            [goog.string :as gstring]))


(def ^:const API_URI_PATTERN "/api/bond/organizations/%s/holdings")

(defn load-holdings!
  "Fetch the holdings for a given organization"
  ([firm-id] (load-holdings! firm-id nil))
  ([firm-id opts]
   (service/fetch-json!
     (gstring/format API_URI_PATTERN firm-id)
     (select-keys opts [:page :limit])
     {:path [:holdings]
      :on-error {:title "Unable to Fetch Holdings"
                 :message "An unknown error occurred while
                          attempting to fetch holdings."}})))

(defn clear-holdings!
  []
  (service/clear-path! [:holdings]))

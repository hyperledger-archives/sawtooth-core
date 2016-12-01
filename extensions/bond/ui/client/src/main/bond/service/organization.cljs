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

(ns bond.service.organization
  (:require [sawtooth.service.common :as service]))

(def ^:const API_URI "/api/bond/organizations")

(defn organizations!
  "Fetch orgs from server"
  []
  (service/fetch-json! API_URI
                       {:path [:organizations]
                        :on-error {:title "Unable to fetch organizations"
                                   :message "An unknown error occurred while
                                            attempting to fetch organizations."}}))

(defn organization!
  "Fetches a single org from server"
  [id]
  (service/fetch-json! (str API_URI "/" id)
                       {:path [:organization]
                        :on-error {:title "Unable to fetch organization"
                                   :message "An unknown error occurred while
                                            attempting to fetch organization."}}))

(defn clear-organizations! []
  (service/clear-path! [:organizations]))

(defn clear-organization! []
  (service/clear-path! [:organization]))

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
(ns mktplace.components.participants
  (:require [om.core :as om]
            [sablono.core :as html :refer-macros [html]]
            [mktplace.routes :as routes]))

(defn participant-link
  "Displays a link for a given participant."
  [participant]
  (html
    [:a.participant-link
     {:href (routes/dashboard-path {:participant-id (:id participant)})}
     (:name participant)]))

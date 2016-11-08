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
(ns mktplace.components.sell-offer-form-test
  (:require [cljs.test :refer-macros [deftest testing is]]
            [om.core :as om]
            [sawtooth.test-common :as tcomm
             :refer-macros [with-container]]
            [mktplace.components.offers :refer [sell-offer-form]]))

(defn- mount-with-holdings [parent assets holdings]
  (om/root sell-offer-form
           {:participant {:holdings holdings}
            :assets assets}
           {:target parent}))

(deftest offer-form-participant-with-no-holdings
  (with-container c
    (mount-with-holdings c [] [])

    (is (= "You have no holdings!" (tcomm/text c)))))


(deftest offer-form-with-holdings
  (with-container c
    (mount-with-holdings
      c
      [{:id "a1"
        :asset-type "12345"
        :name "/asset/type/a1"
        :description "First asset"}
       {:id "a2"
        :asset-type "98765"
        :name "/asset/type/a2"
        :description "Second asset"}]
      [{:id "2"
        :asset "a2"
        :name "/holding/type2/name2"
        :count 100}
       {:id "1"
        :asset "a1"
        :name "/holding/type1/name1"
        :count 10}])

    (let [input (first (tcomm/query "select[name=input]"))
          options (tcomm/children input)]
      (is (= 2 (count options)))
      (is (= "/holding/type1/name1 (/asset/type/a1)" (tcomm/text (first options))))
      (is (= "/holding/type2/name2 (/asset/type/a2)" (tcomm/text (second options)))))

    (let [output (first (tcomm/query "select[name=output]"))
          options (tcomm/children output)]
      (is (= 2 (count options)))
      (is (= "/holding/type1/name1 (/asset/type/a1)" (tcomm/text (first options))))
      (is (= "/holding/type2/name2 (/asset/type/a2)" (tcomm/text (second options)))))))

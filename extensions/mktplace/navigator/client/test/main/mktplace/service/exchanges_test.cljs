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
(ns mktplace.service.exchanges-test
  (:require [cljs.test :refer-macros [deftest testing is async]]
            [mktplace.service.exchange :as exchanges]
            [cljs.pprint :as pprint]))


(deftest test-compute-model-holdings-single-offer
  (let [initial-holding {:id "initial-holding"
                         :asset "asset1-id"
                         :count 10
                         :name "/holding/asset1"}
        final-holding {:id "final-holding"
                       :asset "asset3-id"
                       :count 15
                       :name "/holding/asset3"}

        offers [{:ratio 2.0
                 :input {:id "offer-input-holding"
                         :asset "asset1-id"
                         :count 5
                         :name "/holding/offer/asset1"}
                 :output {:id "offer-output-holding"
                          :asset "asset3-id"
                          :count 10
                          :name "/holding/offer/asset3"}}]
        quantity 1]

    (testing "With no initial or final holdings"
      (is (= 2
             (count (exchanges/compute-model-holdings offers nil nil 1))))
      (is (= (exchanges/compute-model-holdings offers nil nil 1)
          [{:left nil
            :right {:id "offer-input-holding"
                    :asset "asset1-id"
                    :count 5
                    :name "/holding/offer/asset1"}}
           {:left {:id "offer-output-holding"
                   :asset "asset3-id"
                   :count 10
                   :name "/holding/offer/asset3"}
            :right nil}])))

    (testing "with initial and final holdings"
      (is (= 2
             (count (exchanges/compute-model-holdings offers initial-holding final-holding quantity))))
      (is (= (exchanges/compute-model-holdings offers initial-holding final-holding quantity)
             [{:left {:id "initial-holding"
                      :asset "asset1-id"
                      :count 9
                      :name "/holding/asset1"}
               :right {:id "offer-input-holding"
                       :asset "asset1-id"
                       :count 6
                       :name "/holding/offer/asset1"}}
              {:left {:id "offer-output-holding"
                      :asset "asset3-id"
                      :count 8
                      :name "/holding/offer/asset3"}
               :right {:id "final-holding"
                       :asset "asset3-id"
                       :count 17
                       :name "/holding/asset3"}}])))))

(deftest test-compute-model-holdings-multiple-offers
  (testing "with multiple offers"
    (let [initial-holding {:id "initial-holding"
                           :asset "asset1-id"
                           :count 10
                           :name "/holding/asset1"}
          final-holding {:id "final-holding"
                         :asset "asset3-id"
                         :count 15
                         :name "/holding/asset3"}

          offers [{:ratio 2.0
                   :input {:id "offer1-input-holding"
                           :asset "asset1-id"
                           :count 5
                           :name "/holding/offer1/asset1"}
                   :output {:id "offer1-output-holding"
                            :asset "asset2-id"
                            :count 10
                            :name "/holding/offer1/asset2"}}
                  {:ratio 0.5
                   :input {:id "offer2-input-holding"
                           :asset "asset2-id"
                           :count 10
                           :name "/holding/offer2/asset2"}
                   :output {:id "offer2-output-holding"
                            :asset "asset3-id"
                            :count 10
                            :name "/holding/offer2/asset3"}}]
          quantity 1
          computed-holdings (exchanges/compute-model-holdings offers
                                                              initial-holding
                                                              final-holding
                                                              quantity)]
      (is (= 3 (count computed-holdings)))
      (is (= [{:left {:id "initial-holding"
                      :asset "asset1-id"
                      :count 9
                      :name "/holding/asset1"}
               :right {:id "offer1-input-holding"
                       :asset "asset1-id"
                       :count 6
                       :name "/holding/offer1/asset1"}}
              {:left {:id "offer1-output-holding"
                      :asset "asset2-id"
                      :count 8
                      :name "/holding/offer1/asset2"}
               :right {:id "offer2-input-holding"
                       :asset "asset2-id"
                       :count 12
                       :name "/holding/offer2/asset2"}}
              {:left {:id "offer2-output-holding"
                      :asset "asset3-id"
                      :count 9
                      :name "/holding/offer2/asset3"}
               :right {:id "final-holding"
                       :asset "asset3-id"
                       :count 16
                       :name "/holding/asset3"}}]
             computed-holdings)))))

(deftest test-compute-model-holdings-no-offers
  (testing "modeling holding transfers"
     (let [initial-holding {:id "initial-holding"
                           :asset "asset1-id"
                           :count 10
                           :name "/holding/asset1-1"}
          final-holding {:id "final-holding"
                         :asset "asset1-id"
                         :count 15
                         :name "/holding/asset1-2"}
          computed-holdings (exchanges/compute-model-holdings []
                                                              initial-holding
                                                              final-holding
                                                              2)]
       (is (= 1 (count computed-holdings)))
       (is (= [{:left {:id "initial-holding"
                       :asset "asset1-id"
                       :count 8
                       :name "/holding/asset1-1"}
                :right {:id "final-holding"
                        :asset "asset1-id"
                        :count 17
                        :name "/holding/asset1-2" }}]
              computed-holdings)))))

(deftest test-compute-model-holdings-non-consumable
  (testing "modeling holdings with non-consumables"
    (let [initial-holding {:id "initial-holding"
                           :asset "token-asset-id"
                           :count 1
                           :asset-settings {:consumable false}
                           :name "/holding/tokens"}
          final-holding {:id "final-holding"
                         :asset "USD"
                         :count 0
                         :name "/holding/USD"}

          offers [{:ratio 1000
                   :input {:id "offer-input-holding"
                           :asset "token-asset-id"
                           :asset-settings {:consumable false}
                           :count 1
                           :name "/holding/offer/tokens"}
                   :output {:id "offer-output-holding"
                            :asset "USD"
                            :count 1000000
                            :name "/holding/offer/USD"}}]
          quantity 1
          computed-holdings (exchanges/compute-model-holdings
                              offers initial-holding final-holding quantity)]
      (is (= 2 (count computed-holdings)))
      (is (= [{:left {:id "initial-holding"
                      :asset "token-asset-id"
                      :count 1
                      :asset-settings {:consumable false}
                      :name "/holding/tokens"}
               :right {:id "offer-input-holding"
                       :asset "token-asset-id"
                       :asset-settings {:consumable false}
                       :count 1
                       :name "/holding/offer/tokens"}}
               {:left {:id "offer-output-holding"
                       :asset "USD"
                       :count 999000
                       :name "/holding/offer/USD"}
                :right {:id "final-holding"
                        :asset "USD"
                        :count 1000
                        :name "/holding/USD"}}]
             computed-holdings)))))

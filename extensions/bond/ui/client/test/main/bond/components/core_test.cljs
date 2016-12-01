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

(ns bond.components.core-test
  (:require [cljs.test :refer-macros [deftest testing are is async use-fixtures]]
            [bond.components.core :as core]))

(deftest bond-price-parse-test
  (are [price perc] (= (core/price->perc-of-par price) perc)
       "100" 100
       "98-4" 98.125
       "105-07" 105.21875
       "99-31+" 99.984375
       "101-13 5/8" 101.42578125
       "98-05.875" 98.18359375
       "102-27 3/4+" 102.8828125
       "31-4.159+" 31.14559375
       "141-13 0/2+" 141.421875))

(deftest bond-price->yield-test
  (are [price coup yield] (= (core/price->yield price coup) yield)
       "100" "0" 0
       "98-4" "4 3/8" 4.45859872611465
       "102-15+" "1 1/4" 1.2196981247141332
       "107-20 5/8" 1.5 1.393475342018362
       "31-4 1/5" 92 295.52298735193733
       "141-12 1/3" "5" 3.536432623590953))

(deftest test-yield->price
  (are [yield coup price] (< (- (core/yield->price yield coup) price) 0.00001)
       0 "0" 100
       4.45859872611465 "4 3/8" 98.125
       1.2196981247141332 "1 1/4" 102.484375
       1.393475342018362 1.5 107.64453125
       295.52298735193733 92 31.13125
       3.536432623590953  "5" 141.385417))

(deftest test-format-price
  (are [price price-string] (= (core/format-price price) price-string)
       100 "100"
       98.125 "98-4"
       102.484375 "102-15+"
       107.64453125 "107-20 5/8"
       31.13125 "31-4 1/8"
       141.385417 "141-12 1/4"))

(deftest bond->name-test
  (are [name bond] (= name (core/bond->name bond))
       "ABIBB 3 5/8 02/01/26 Corp" {:coupon-rate "3.65"
                                    :issuer "ABIBB"
                                    :maturity-date "02/01/2026"}
       "T 1 3/8 05/31/21 Govt" {:coupon-rate "1.375"
                                :issuer "T"
                                :maturity-date "05/31/2021"}))

(deftest isin-valid?-test
  (are [isin result] (= (core/isin-valid? isin) result)
       "US0378331005" true
       "AU0000XVGZA3" true
       "US22160KAF21" true
       "US71647NAE94" true
       "arglebargle" false
       "42" false
       "US22160AKF11" false
       "US7167ANAE94" false))

(deftest test-cusip-valid?

  (are [cusip result] (= (core/cusip-valid? cusip) result)
       "037833100" true
       "17275R102" true
       "38259P508" true
       "594918104" true
       "68389X105" true

       "arglebargle" false
       "43" false

       ;bad checksums
       "68389X10X" false
       "037833109" false))

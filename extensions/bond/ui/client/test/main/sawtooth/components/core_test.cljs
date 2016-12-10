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

(ns sawtooth.components.core-test
  (:require [cljs.test :refer-macros [deftest testing are is async use-fixtures]]
            [sawtooth.math :as math]
            [sawtooth.components.core :as components]))

(deftest test-classes
  (are [x y] (= x y)
       nil (components/classes nil)
       "" (components/classes {})
       "a" (components/classes {:a true})
       "a b" (components/classes {:a true :b 5})

       "b" (components/classes {:a nil :b [:x]})
       "a" (components/classes {:a "something" :b false})
       "x" (components/classes {nil true :x true})))

(deftest test->boolean
  (are [x y] (= x y)
       true (components/->boolean "true")
       true (components/->boolean "True")
       true (components/->boolean nil true)

       false (components/->boolean "false")
       false (components/->boolean "False")
       false (components/->boolean "1")
       false (components/->boolean "")
       false (components/->boolean nil)))

(deftest test->num
  (are [s n] (= (components/->num s) n)
       "1" 1
       "0" 0
       "-1" -1
       "100.25" 100.25
       "-3.141" -3.141
       "1/2" 0.5
       "-128/8" -16
       "1 1/2" 1.5
       "-7 3/4" -7.75
       "3863840123594" 3863840123594
       "-7982709598343" -7982709598343
       "arglebargle" nil
       {:a 1} nil)
  (are [s default-value n] (= (components/->num s default-value) n)
       "1" 0 1
       "0" 1 0
       "-128/8" "UNCONVERTABLE" -16
       "3863840123594" :no 3863840123594
       "arglebargle" 0 0
       {:a 1} "CAN'T CONVERT" "CAN'T CONVERT"))

(deftest test->frac
  (are [n frac] (= (components/->frac n) frac)
       1 "1"
       0 "0"
       42 "42"
       0.5 "1/2"
       0.999 "7/8"
       1.75 "1 3/4"
       -10 "-10"
       -22.5 "-22 1/2")
  (are [n denom frac] (= (components/->frac n denom) frac)
       1 10 "1"
       0 2 "0"
       0.5 9 "4/9"
       1.75 64 "1 3/4"
       -22.852 16 "-22 13/16"))

(deftest test->float
  (testing "correct values"
    (are [s n] (> 0.000001 (math/abs (- (components/->float s) n)))
         "0.01" 0.01
         "12" 12
         "12.0" 12.0
         "1.122" 1.122
         "2.0" 2
         "2.03" 2.03))
  (testing "fail values"
    (are [s x] (= (components/->float s) x)
         "1." nil
         nil nil
         "x" nil)))

(deftest test-make-page-numbers
  (testing "with all pages visible"
    (is (= [0 1 2]
           (components/make-page-numbers 3 1 6))))
  (testing "with lowest pages visible"
    (is (= [0 1 2 3 4 :... 9]
           (components/make-page-numbers 10 1 6))))

  (testing "with middle pages visible"
    (is (= [0 :... 3 4 5 :... 9]
           (components/make-page-numbers 10 4 6))))

  (testing "with end pages visible"
    (is (= [0 :... 6 7 8 9]
           (components/make-page-numbers 10 10 6)))))

/**
 * Copyright 2016 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ------------------------------------------------------------------------------
 */
"use strict";
/**
 * Created by staite on 10/19/2015.
 */
var Fraction = require('fraction.js');

module.exports = {

    orderJsonKeysAlphabetically: orderJsonKeysAlphabetically,
    toFraction: toFraction,
    dec2frac : dec2frac,
};


function orderJsonKeysAlphabetically(unorderedObject){
    var orderedObject = {};
    Object.keys(unorderedObject).sort().forEach(function(key) {
        orderedObject[key] = unorderedObject[key];
    });
    unorderedObject = orderedObject;
}

function toFraction(d) {
    var f = new Fraction(d);
    return {numerator: f.n, denominator: f.d};
}

function dec2frac(d) {
    var frac = toFraction(d);
    return frac.numerator + '/' + frac.denominator;
}

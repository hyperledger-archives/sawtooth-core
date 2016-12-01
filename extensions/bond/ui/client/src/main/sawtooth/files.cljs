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

(ns sawtooth.files)

(defn upload->file
  "Takes file upload event and returns the (first) file uploaded"
  [e]
  (aget (.. e -target -files) 0))

(defn file->string
  "Asynchonously reads a text file sends the content to a callback"
  [file cb]
  (let [reader (js/FileReader.)]
    (set! (.-onload reader) (fn [e] (cb (.. e -target -result))))
    (.readAsText reader file)))

(defn upload->string
  [e cb]
  "Asynchonously take an upload event and sends the content to a callback"
  (file->string (upload->file e) cb))

(defn text-file-url!
  "Builds a text file out of a string and sets it to a URL.
  Cleans up after itself by destroying an old url if passed."
  ([text] (text-file-url! text nil))
  ([text old-url]
  (let [blob (js/Blob. (array text) (js-obj "type" "text/plain"))]
    (when old-url (.revokeObjectURL js/window.URL old-url))
    (.createObjectURL js/window.URL blob))))

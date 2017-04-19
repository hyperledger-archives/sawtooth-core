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

(ns bond.components.footer
  (:require [om.core :as om]
            [sablono.core :refer-macros [html]]
            [sawtooth.components.core :refer-macros [when-new-block]]
            [bond.routes :as routes]))

(defn footer [data owner]
  (reify
    om/IWillReceiveProps
    (will-receive-props [_ next-state]
      (when-new-block owner next-state
        (om/set-state! owner :updated! true)))

    om/IDidUpdate
    (did-update [_ prev-props prev-state]
      (when (om/get-state owner :updated!)
        (js/setTimeout #(om/set-state! owner :updated! false) 1000)))

    om/IRenderState
    (render-state [_ {:keys [updated!]}]
      (html
        [:div.footer
         [:div.container
          [:div.col-xs-2
           [:p.text-muted
            "© Intel 2016"]]
          [:div.col-xs-2
           [:p.text-muted
            [:a {:href "http://www.intel.com/content/www/us/en/privacy/intel-privacy-notice.html"
                 :target "_blank"}
             "Privacy Notice"]]]

          [:div.col-xs-2
           [:p.text-muted
            [:a {:href "https://www-ssl.intel.com/content/www/us/en/legal/terms-of-use.html "
                 :target "_blank"}
             "Terms of Use"]]]
          (when-let [block (:block data)]
            [:div.col-xs-offset-4.col-xs-2
             [:p.text-muted
              [:a
               {:href (routes/transaction-history)
                :class (if updated! "block-updated")}
               (str "Block: " (:blockid block) " (" (:blocknum block) ")")]]])]]))))

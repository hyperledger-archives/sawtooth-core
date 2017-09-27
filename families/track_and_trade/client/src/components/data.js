/**
 * Copyright 2017 Intel Corporation
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
 * ----------------------------------------------------------------------------
 */
'use strict'

const m = require('mithril')
const GoogleMapsLoader = require('google-maps')

// Google Maps Dev API key
GoogleMapsLoader.KEY = 'AIzaSyAF75RJvbpC-NhYERNuWadktXnEkrmGDDI'
let google = null

const MapWidget = {
  view (vnode) {
    return m('#map-container')
  },

  oncreate (vnode) {
    GoogleMapsLoader.load(goog => {
      google = goog
      const coordinates = vnode.attrs.coordinates.map(coord => ({
        lat: coord.latitude,
        lng: coord.longitude
      }))

      const container = document.getElementById('map-container')
      vnode.state.map = new google.maps.Map(container, { zoom: 4 })
      vnode.state.markers = coordinates.map(position => {
        return new google.maps.Marker({ position, map: vnode.state.map })
      })

      vnode.state.path = new google.maps.Polyline({
        map: vnode.state.map,
        path: coordinates,
        geodesic: true,
        strokeColor: '#FF0000'
      })

      vnode.state.bounds = new google.maps.LatLngBounds()
      coordinates.forEach(position => vnode.state.bounds.extend(position))
      vnode.state.map.fitBounds(vnode.state.bounds)
    })
  },

  onbeforeupdate (vnode, old) {
    // Coordinates exist and have changed
    return vnode.attrs.coordinates &&
      vnode.attrs.coordinates.length !== old.attrs.coordinates.length
  },

  onupdate (vnode) {
    const coordinates = vnode.attrs.coordinates.map(coord => ({
      lat: coord.latitude,
      lng: coord.longitude
    }))

    vnode.state.markers.forEach(marker => marker.setMap(null))
    vnode.state.markers = coordinates.map(position => {
      return new google.maps.Marker({ position, map: vnode.state.map })
    })

    vnode.state.path.setPath(coordinates)
    coordinates.forEach(position => vnode.state.bounds.extend(position))
    vnode.state.map.fitBounds(vnode.state.bounds)
  }
}

module.exports = {
  MapWidget
}

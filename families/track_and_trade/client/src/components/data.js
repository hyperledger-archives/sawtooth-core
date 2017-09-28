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
const Chart = require('chart.js')
const GoogleMapsLoader = require('google-maps')

// Google Maps Dev API key
GoogleMapsLoader.KEY = 'AIzaSyAF75RJvbpC-NhYERNuWadktXnEkrmGDDI'
let google = null

const LineGraphWidget = {
  view (vnode) {
    return m('canvas#graph-container', { width: '100%' })
  },

  parseUpdates (updates) {
    return updates.map(d => ({
      t: d.timestamp * 1000,
      y: d.value,
      reporter: d.reporter.name
    }))
  },

  oncreate (vnode) {
    const ctx = document.getElementById('graph-container').getContext('2d')

    vnode.state.graph = new Chart(ctx, {
      type: 'line',
      data: {
        datasets: [{
          data: this.parseUpdates(vnode.attrs.updates),
          fill: false,
          pointStyle: 'triangle',
          pointRadius: 8,
          borderColor: '#ff0000',
          lineTension: 0
        }]
      },
      options: {
        legend: {
          display: false
        },
        tooltips: {
          bodyFontSize: 14,
          displayColors: false,
          custom: model => {
            if (model.body) {
              const index = model.dataPoints[0].index
              const reporter = vnode.state.graph.data.datasets[0]
                .data[index].reporter
              const value = model.body[0].lines[0]
              model.body[0].lines[0] = `${value} (from ${reporter})`
            }
          }
        },
        responsive: true,
        scales: {
          xAxes: [{
            type: 'time',
            offset: true,
            display: true,
            time: {
              minUnit: 'second',
              tooltipFormat: 'MM/DD/YYYY, h:mm:ss a'
            },
            ticks: {
              major: {
                fontStyle: 'bold',
                fontColor: '#ff0000'
              }
            }
          }],
          yAxes: [{
            type: 'linear',
            offset: true,
            display: true
          }]
        }
      }
    })
  },

  onupdate (vnode) {
    const data = this.parseUpdates(vnode.attrs.updates)
    vnode.state.graph.data.datasets[0].data = data
    vnode.state.graph.update()
  }
}

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
  LineGraphWidget,
  MapWidget
}

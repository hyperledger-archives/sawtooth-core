/**
 * Copyright 2016 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * No license under any patent, copyright, trade secret or other intellectual
 * property right is granted to or conferred upon you by disclosure or delivery
 * of the Materials, either expressly, by implication, inducement, estoppel or
 * otherwise. Any license under such intellectual property rights must be
 * express and approved by Intel(R) in writing.
 */
/* globals __dirname */
"use strict";

var path = require('path');
var webpack = require('webpack');

module.exports = {
    entry: ['babel-polyfill', path.join(__dirname, 'src', 'js', 'library.js')],
    output: {
        path: path.join(__dirname, 'lib'),
        filename: 'deps_library.js',
        libraryTarget: "commonjs",
    },
    module: {
        loaders: [
            {
                test: /.json$/,
                loaders: ['json-loader']
            },
            {
                test: /.js$/,
                //exclude: /node_modules/,
                loader: 'babel',
                query: {
                    presets: ['es2015-native-modules']
                }
            },
        ]
    },
    plugins: [
        new webpack.LoaderOptionsPlugin({
            minimize: true,
            debug: false,
        }),
        new webpack.optimize.UglifyJsPlugin({
            mangle: {
                except: ['Array', 'BigInteger', 'Boolean','Buffer',
                         'ECPair', 'Function', 'Number', 'Point',
                         /*'encodeCBOR', '_pushFloat'*/
                ]
            },
            compress: {
                warnings: false
            },
            output: {
                comments: false
            },
            sourceMap: false
        }),
    ],
    resolve: {
        modules: [path.join(__dirname, 'src', 'js'), 'node_modules'],
        alias: {
            fs: 'dummy.js',
            clipboard: 'clipboard/dist/clipboard.js',
        }
    },
};

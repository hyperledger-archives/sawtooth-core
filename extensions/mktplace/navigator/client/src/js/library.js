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
"use strict";

import {message, networks, ECPair} from 'bitcoinjs-lib';
import {decode} from 'bs58check';
import {Encoder} from 'cbor';
import * as frac from 'fraction.js';
import * as socket_io from 'socket.io-client';

/**
 * A ratio class for encoding ratio CBOR as a float
 */
export class Ratio {
    constructor(n) {
        this.n = n;
    }

    encodeCBOR(encoder) {
        encoder._pushFloat(this.n);
    }
}

/**
 * Limited bitcoinlib-js exports
 */
export const  bitcoin = {
    /**
     * The object to hash
     */
    hash: (obj) =>
        message.magicHash(Encoder.encode(obj), networks.bitcoin).toString('hex'),

    /**
     * @params publicKey: String - base58check-encoded public key.
     */
    addressFromPublicKey: (publicKeyStr) => {
        let keyPair = ECPair.fromPublicKeyBuffer(decode(publicKeyStr), networks.bitcoin);
        return keyPair.getAddress();
    },

    publicKeyHex: (keyPair) => {
        return keyPair.getPublicKeyBuffer().toString('hex');
    },

    /**
     * Converts a hex string to base 64
     */
    hexToBase64: (str) =>
        new Buffer(str, 'hex').toString('base64'),

    ECPair,

    sign: (keyPair, msg) =>
        message.sign(keyPair, Encoder.encode(msg), networks.bitcoin).toString('base64'),

};

/**
 * Exports fraction
 */
export const Fraction = frac;
export const Clipboard = require('clipboard');

/**
 * Exports socket.io-client
 */
export const socket = {
    io: socket_io
};

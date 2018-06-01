# Copyright 2017 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

import unittest
import logging
import json
import urllib.request
import urllib.error
import base64
import pytest
import os, signal
import re
import subprocess
import requests
import binascii
import codecs
import time

from sawtooth_intkey.intkey_message_factory import IntkeyMessageFactory
from sawtooth_sdk.processor.exceptions import InvalidTransaction
from urllib.error import HTTPError
import sawtooth_rest_api.exceptions as errors
from struct import *

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
WAIT = 300

def helper_msg(msg='assert OK'):
        print ("\n")
        print (msg)
        return True

def check_stop_validator():
    for line in os.popen("ps ax | grep " + 'sawtooth-validator' + " | grep -v grep"):
        fields = line.split()
        pid = fields[0]
    for i in range(3):
        os.kill(int(pid), signal.SIGINT)
        
def check_kill_validator():
    for line in os.popen("ps ax | grep " + 'sawtooth-validator' + " | grep -v grep"):
        fields = line.split()
        pid = fields[0]
    for i in range(3):
        os.kill(int(pid), signal.SIGKILL)


def get_blocks():
    response = query_rest_api('/blocks')
    return response['data']


def get_block_info_config():
    bic = BlockInfoConfig()
    bic.ParseFromString(get_state(CONFIG_ADDRESS))
    return bic


def get_block_info(block_num):
    bi = BlockInfo()
    bi.ParseFromString(get_state(create_block_address(block_num)))
    return bi

def get_state_list():
    response = query_rest_api('/state')
    return response['data']


def get_state(address):
    response = query_rest_api('/state/%s' % address)
    return base64.b64decode(response['data'])


def post_batch(batch, header=None, resourceid=None,stop=0, Empty=None):
    if header==None:
        headers = {'Content-Type': 'application/octet-stream'}
    if header== "wrong_header":
        headers = {'Content-Type': 'application/json'}
    if stop==0:
        response = query_rest_api(
            '/batches', data=batch, headers=headers)
    elif stop==1:
        response = query_rest_api(
            '/batches', data=batch, headers=headers,stop=1)
    if Empty==None:
        response = query_rest_api(
            '/batches', data=batch, headers=headers)
    elif Empty==True:
        response = query_rest_api(
            '/batches', data=bytearray(), headers=headers)      
    if resourceid == "invalid resource id":
        response['link']="http://localhost:8008/batch_statuses?id=d3424"
        response = submit_request('{}&wait={}'.format(response['link'], WAIT))
    #print (response)
    return response

def query_rest_api(suffix='', data=None, headers=None, stop=0):
    if headers is None:
        headers = {}
    url = 'http://localhost:8008' + suffix
    if stop==1:
        return submit_request(urllib.request.Request(url, data, headers),stop=1)
    else:
        return submit_request(urllib.request.Request(url, data, headers))


def submit_request(request,stop=0):
        if stop==1:
            check_stop_validator()
        
        response = urllib.request.urlopen(request).read().decode('utf-8')
       
        return json.loads(response)

def make_batches(keys):
    imf = IntkeyMessageFactory()
    return [imf.create_batch([('set', k, 0)]) for k in keys]


def test_post_batch_wrong_header():
        """Tests that BlockInfo transactions are injected and committed for
        each block that is created by submitting intkey batches and then
        confirming that block info batches are in the final state.
        """
        initial_state_length = len(get_state_list())
        batches = make_batches('a')

        # Assert all block info transactions are committed
        for i, batch in enumerate(batches):
                
            #with pytest.raises(HTTPError):
            try:
                response=post_batch(batch, header="wrong_header")
            except urllib.error.HTTPError as e:
                errdata = e.file.read().decode("utf-8")
                error = json.loads(errdata)
                #print (error)
                assert (json.loads(errdata)['error']['code']) == 42 
                assert e.code == 400
                #print (e.code)
        final_state_length= len(get_state_list())
        assert initial_state_length == final_state_length and helper_msg(), "Failed state lenghth are not same"
    
def test_post_batch_invalid_resourceid():
        """Tests that BlockInfo transactions are injected and committed for
        each block that is created by submitting intkey batches and then
        confirming that block info batches are in the final state.
        """
        initial_state_length = len(get_state_list())
        batches = make_batches('a')

        # Assert all block info transactions are committed
        for i, batch in enumerate(batches):
                
            #with pytest.raises(HTTPError):
            try:
                response=post_batch(batch, resourceid="invalid resource id")
            except urllib.error.HTTPError as e:
                errdata = e.file.read().decode("utf-8")
                error = json.loads(errdata)
                #print (error)
                assert (json.loads(errdata)['error']['code']) == 60
                assert e.code == 400
                #print (e.code)
        final_state_length= len(get_state_list())
        assert initial_state_length == final_state_length and helper_msg(), "Failed state lenghth are not same"

def test_post_Empty_Batch():
        #initial_state_length = len(get_state_list())
        batches = make_batches('a')
        
        for i, batch in enumerate(batches):
            try:
                response=post_batch(batch, Empty=True)
            except urllib.error.HTTPError as e:
                errdata = e.file.read().decode("utf-8")
                error = json.loads(errdata)
                #print (error)
                assert (json.loads(errdata)['error']['code']) == 34
                assert e.code == 400
            
def test_post_batch_validator_disconnect():
        """Tests that BlockInfo transactions are injected and committed for
        each block that is created by submitting intkey batches and then
        confirming that block info batches are in the final state.
        """
        #initial_state_length = len(get_state_list())
        batches = make_batches('a')

        # Assert all block info transactions are committed
        for i, batch in enumerate(batches):
                
            #with pytest.raises(HTTPError):
            try:
                response=post_batch(batch, stop=1)
            except urllib.error.HTTPError as e:
                errdata = e.file.read().decode("utf-8")
                error = json.loads(errdata)
                #print (error)
                assert (json.loads(errdata)['error']['code']) == 18
                assert e.code == 503
                #print (e.code)
                
def test_start_validator():
        time.sleep(10)
        check_kill_validator()
        check_status_code= "sudo -u sawtooth sawtooth-validator -vv"
        subprocess.Popen(check_status_code, shell=True, stderr=subprocess.PIPE)
        

    
        
'''
def test_post_batch_validator_timeout():
        
        """Tests that BlockInfo transactions are injected and committed for
        each block that is created by submitting intkey batches and then
        confirming that block info batches are in the final state.
        """
    
        initial_state_length = len(get_state_list())
        batches = make_batches('a')
        
        # Assert all block info transactions are committed
        for i, batch in enumerate(batches):
          
            try:
                response=post_batch(batch, stop=0)
            except urllib.error.HTTPError as e:
                errdata = e.file.read().decode("utf-8")
                error = json.loads(errdata)
                assert (json.loads(errdata)['error']['code']) == 17
                assert e.code == 503
        assert initial_state_length == final_state_length and helper_msg(), "Failed state lenghth are not same"    
'''           


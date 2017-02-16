# Copyright 2016 Intel Corporation
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

import gossip.signed_object as SigObj

from sawtooth_signing import pbct_nativerecover as signing
from gossip.common import cbor2dict
from gossip.signed_object import SignedObject
from gossip.node import Node


# from utils.py in txintegration
def generate_private_key():
    return signing.encode_privkey(signing.generate_privkey(), 'wif')


# get_verifying_key always raises a warning


class TestSignedObject(unittest.TestCase):

    def test_init(self):
        # Trival test creates a SignedObject
        # check that everything initalizes as expected
        temp = SignedObject({"TestSignatureDictKey": "test"}, "TestSignatureDictKey")
        self.assertEqual(temp.SignatureDictKey, "TestSignatureDictKey")
        self.assertEqual(temp.dump(), {"TestSignatureDictKey": "test", "PublicKey": None})
        self.assertEqual(temp.__repr__(), temp.serialize())
        self.assertIsNotNone(temp.Identifier)
        temp._identifier = None
        self.assertIsNotNone(temp.Identifier)

    def test_is_valid(self):
        # Verify that is_valid only returns true if working with a valid
        # Signed Object
        # test a valid signature
        temp = SignedObject({"TestSignatureDictKey": "test"}, "TestSignatureDictKey")
        signing_key = generate_private_key()
        temp.sign_object(signing_key)
        self.assertTrue(temp.is_valid("unused"))

        # test OriginatorID
        ogid = temp.OriginatorID
        self.assertTrue(temp.verify_signature(ogid))

        # test invalid OriginatorID
        self.assertFalse(temp.verify_signature("invalid"))

    def test_is_valid_no_public_key(self):
        # Verify that is_valid only returns true if working with a valid
        # SignedObject
        # test a valid signature
        temp = SignedObject({"TestSignatureDictKey": "test"},
                            "TestSignatureDictKey")
        self.assertFalse(temp.is_valid("invalid"))

    def test_valid_signature(self):
        signing_key = SigObj.generate_signing_key()
        pub_key = signing.generate_pubkey(signing_key)
        temp = SignedObject({"PublicKey": pub_key})
        # test valid signature
        temp.sign_object(signing_key)
        self.assertTrue(temp.is_valid("valid"))

    def test_invalid_signature(self):
        signing_key = SigObj.generate_signing_key()
        pub_key = signing.generate_pubkey(signing_key)
        temp = SignedObject({"PublicKey": pub_key})

        invalid_signing_key = SigObj.generate_signing_key()
        # test invalid signature
        temp.sign_object(invalid_signing_key)
        self.assertFalse(temp.is_valid("invalid"))

    def test_is_valid_assertion(self):
        # Test that an AssertionError is raised when dealing with a
        # default SignedObject() because it does not have an signature
        temp2 = SignedObject()
        try:
            # will always print error
            # Does not have a signautre when created with default paramaters
            temp2.verify_signature("unused")
            # should throw an an assertion error, Otherwise fail test
            self.fail("Should have raised an Assertion Error")

        except AssertionError, e:
            self.assertIsInstance(e, AssertionError)

    def test_signed_node(self):
        # Verify that signed_node and sign_object does not invalidate the
        # signed object and can be returned to original
        # create initial signed object
        temp = SignedObject({"TestSignatureDictKey": "test"}, "TestSignatureDictKey")
        # save origanl OriginatorID before creating node
        idBeforeNode = temp.OriginatorID

        # create a node instance
        key = generate_private_key()
        sigkey = SigObj.generate_signing_key(wifstr=key)
        nodeid = SigObj.generate_identifier(sigkey)
        testNode = Node(name="testNode", signingkey=sigkey, identifier=nodeid)

        temp.sign_from_node(testNode)
        # save new OriginatorID after the
        idAfterNode = temp.OriginatorID

        self.assertNotEqual(idAfterNode, idBeforeNode)
        # check that the signed_object signature is still valid and reset
        # OrignatorId back to original
        self.assertTrue(temp.is_valid("unused parameter"))
        self.assertNotEqual(temp.OriginatorID, idBeforeNode)

    def test_sign_node_assertion(self):
        # Test that an assertion error is thrown when a node is passed
        # that does not have a Signingkey
        # create SignedObject
        temp = SignedObject({"TestSignatureDictKey": "test"}, "TestSignatureDictKey")
        # create a Node that does not have a signingKey
        testNode = Node(name="badNode")
        try:
            # should throw an an assertion error, Otherwise fail test
            temp.sign_from_node(testNode)
            self.fail("Should have raised an Assertion Error")

        except AssertionError, e:
            self.assertIsInstance(e, AssertionError)

    def test_serialize(self):
        # Test that serilazation returns the correct dictionary and that
        # it can be retrieved.
        # create SignedObject
        temp = SignedObject({"TestSignatureDictKey": "test"}, "TestSignatureDictKey")
        # serlize SignedObject
        cbor = temp.serialize()
        # check that the unserilized serilized dictinary is the same
        # as before serilazation
        self.assertEqual(cbor2dict(cbor), temp.dump())

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
 * ------------------------------------------------------------------------------
 */

package client

import (
	"encoding/hex"
	"fmt"
	"github.com/golang/protobuf/proto"
	"sawtooth_sdk/protobuf/batch_pb2"
	"sawtooth_sdk/protobuf/transaction_pb2"
	"strings"
	"time"
)

type TransactionParams struct {
	FamilyName      string
	FamilyVersion   string
	PayloadEncoding string
	Nonce           string
	BatcherPubkey   string
	Dependencies    []string
	Inputs          []string
	Outputs         []string
}

type Encoder struct {
	privkey  []byte
	pubkey   string
	defaults TransactionParams
}

// NewTransactionEncoder constructs a new encoder which can be used to generate
// transactions and batches, and to serialize batches for submitting to the
// REST API.
func NewEncoder(privkey []byte, defaults TransactionParams) *Encoder {
	return &Encoder{
		privkey:  privkey,
		pubkey:   MustEncode(GenPubKey(privkey)),
		defaults: defaults,
	}
}

// -- Transactions --

// NewTransaction Creates a new transaction and handles the construction and
// signing of the transaction header.
func (self *Encoder) NewTransaction(payload []byte, p TransactionParams) *Transaction {
	h := &transaction_pb2.TransactionHeader{
		// Load defaults
		FamilyName:      self.defaults.FamilyName,
		FamilyVersion:   self.defaults.FamilyVersion,
		PayloadEncoding: self.defaults.PayloadEncoding,
		Nonce:           self.defaults.Nonce,
		BatcherPubkey:   self.defaults.BatcherPubkey,

		Inputs:       self.defaults.Inputs,
		Outputs:      self.defaults.Outputs,
		Dependencies: self.defaults.Dependencies,

		// Set unique fields
		PayloadSha512: MustEncode(SHA512(payload)),
		SignerPubkey:  self.pubkey,
	}

	// Override defaults if set
	if p.FamilyName != "" {
		h.FamilyName = p.FamilyName
	}
	if p.FamilyVersion != "" {
		h.FamilyVersion = p.FamilyVersion
	}
	if p.PayloadEncoding != "" {
		h.PayloadEncoding = p.PayloadEncoding
	}
	if p.Nonce != "" {
		h.Nonce = p.Nonce
	}
	if p.BatcherPubkey != "" {
		h.BatcherPubkey = p.BatcherPubkey
	}

	if p.Inputs != nil {
		h.Inputs = p.Inputs[:]
	}
	if p.Outputs != nil {
		h.Outputs = p.Outputs[:]
	}
	if p.Dependencies != nil {
		h.Dependencies = p.Dependencies[:]
	}

	// Generate a nonce if none has been set yet
	if h.Nonce == "" {
		h.Nonce = fmt.Sprintf("%x", time.Now().UTC().UnixNano())
	}

	// If a BatcherPubkey hasn't been set yet, assume its our key
	if h.BatcherPubkey == "" {
		h.BatcherPubkey = self.pubkey
	}

	hb, err := proto.Marshal(h)
	if err != nil {
		panic(err)
	}
	hs := MustEncode(Sign(hb, self.privkey))

	transaction := &transaction_pb2.Transaction{
		Header:          hb,
		HeaderSignature: hs,
		Payload:         payload,
	}

	return (*Transaction)(transaction)
}

// SerializeTransactions serializes the given transactions to bytes for
// transmission to a separate batcher.
func SerializeTransactions(transactions []*Transaction) []byte {
	txns := make([]*transaction_pb2.Transaction, 0, len(transactions))
	for _, tx := range transactions {
		txns = append(txns, tx.ToPb())
	}

	tl := &transaction_pb2.TransactionList{
		Transactions: txns,
	}

	tlb, err := proto.Marshal(tl)
	if err != nil {
		panic(err)
	}

	return tlb
}

// ParseTransactions deserializes the given bytes into a list of transactions.
// The bytes are assumed to be in the format returned by SerializeTransactions.
func ParseTransactions(b []byte) ([]*Transaction, error) {
	tl := &transaction_pb2.TransactionList{}
	err := proto.Unmarshal(b, tl)
	if err != nil {
		return nil, err
	}

	txns := tl.GetTransactions()

	transactions := make([]*Transaction, 0, len(txns))
	for _, tx := range txns {
		transactions = append(transactions, (*Transaction)(tx))
	}

	return transactions, nil
}

// -- Batches --

// NewBatch creates a new batch from the given transactions created by
// NewTransaction. It handles the construction and signing of the batch header.
func (self *Encoder) NewBatch(transactions []*Transaction) *Batch {
	txnIds := make([]string, 0, len(transactions))
	txns := make([]*transaction_pb2.Transaction, 0, len(transactions))
	for _, tx := range transactions {
		txnIds = append(txnIds, tx.Id())
		txns = append(txns, tx.ToPb())
	}

	h := &batch_pb2.BatchHeader{
		SignerPubkey:   self.pubkey,
		TransactionIds: txnIds,
	}

	hb, err := proto.Marshal(h)
	if err != nil {
		panic(err)
	}

	hs := MustEncode(Sign(hb, self.privkey))

	batch := &batch_pb2.Batch{
		Header:          hb,
		HeaderSignature: hs,
		Transactions:    txns,
	}

	return (*Batch)(batch)
}

// SerializeBatches serializes the given batches to bytes in the form expected
// by the REST API.
func SerializeBatches(batches []*Batch) []byte {
	bs := make([]*batch_pb2.Batch, 0, len(batches))
	for _, b := range batches {
		bs = append(bs, b.ToPb())
	}
	bl := &batch_pb2.BatchList{
		Batches: bs,
	}

	blb, err := proto.Marshal(bl)
	if err != nil {
		panic(err)
	}

	return blb
}

// ParseBatches deserializes the given bytes into a list of batches. The bytes
// are assumed to be in the format returned by SerializeBatches.
func ParseBatches(b []byte) ([]*Batch, error) {
	bl := &batch_pb2.BatchList{}
	err := proto.Unmarshal(b, bl)
	if err != nil {
		return nil, err
	}

	bs := bl.GetBatches()

	batches := make([]*Batch, 0, len(bs))
	for _, b := range bs {
		batches = append(batches, (*Batch)(b))
	}

	return batches, nil
}

// -- Encoding --

// MustEncode converts the given byte slice to a lower-case hex-encoded string.
// Panics if encoding fails.
func MustEncode(data []byte) string {
	return strings.ToLower(hex.EncodeToString(data))
}

// MustDecode converts the given lower-case, hex-encoded string to a byte slice
// and panics if decoding fails.
func MustDecode(encoded string) []byte {
	bytes, err := hex.DecodeString(encoded)
	if err != nil {
		panic("Couldn't decode")
	}
	return bytes
}

// -- Wrap Protobuf --

// Wrap the protobuf types so that they do not need to be imported separately.
type Transaction transaction_pb2.Transaction

func (t *Transaction) ToPb() *transaction_pb2.Transaction {
	return (*transaction_pb2.Transaction)(t)
}

// GetId Returns the Transaction ID which can be used to specify this
// transaction as a dependency for other transactions.
func (t *Transaction) Id() string {
	return t.ToPb().GetHeaderSignature()
}

type Batch batch_pb2.Batch

func (b *Batch) ToPb() *batch_pb2.Batch {
	return (*batch_pb2.Batch)(b)
}

// <auto-generated>
//     Generated by the protocol buffer compiler.  DO NOT EDIT!
//     source: transaction.proto
// </auto-generated>
#pragma warning disable 1591, 0612, 3021
#region Designer generated code

using pb = global::Google.Protobuf;
using pbc = global::Google.Protobuf.Collections;
using pbr = global::Google.Protobuf.Reflection;
using scg = global::System.Collections.Generic;
/// <summary>Holder for reflection information generated from transaction.proto</summary>
public static partial class TransactionReflection {

  #region Descriptor
  /// <summary>File descriptor for transaction.proto</summary>
  public static pbr::FileDescriptor Descriptor {
    get { return descriptor; }
  }
  private static pbr::FileDescriptor descriptor;

  static TransactionReflection() {
    byte[] descriptorData = global::System.Convert.FromBase64String(
        string.Concat(
          "ChF0cmFuc2FjdGlvbi5wcm90byLVAQoRVHJhbnNhY3Rpb25IZWFkZXISGgoS",
          "YmF0Y2hlcl9wdWJsaWNfa2V5GAEgASgJEhQKDGRlcGVuZGVuY2llcxgCIAMo",
          "CRITCgtmYW1pbHlfbmFtZRgDIAEoCRIWCg5mYW1pbHlfdmVyc2lvbhgEIAEo",
          "CRIOCgZpbnB1dHMYBSADKAkSDQoFbm9uY2UYBiABKAkSDwoHb3V0cHV0cxgH",
          "IAMoCRIWCg5wYXlsb2FkX3NoYTUxMhgJIAEoCRIZChFzaWduZXJfcHVibGlj",
          "X2tleRgKIAEoCSJICgtUcmFuc2FjdGlvbhIOCgZoZWFkZXIYASABKAwSGAoQ",
          "aGVhZGVyX3NpZ25hdHVyZRgCIAEoCRIPCgdwYXlsb2FkGAMgASgMIjUKD1Ry",
          "YW5zYWN0aW9uTGlzdBIiCgx0cmFuc2FjdGlvbnMYASADKAsyDC5UcmFuc2Fj",
          "dGlvbkIqChVzYXd0b290aC5zZGsucHJvdG9idWZQAVoPdHJhbnNhY3Rpb25f",
          "cGIyYgZwcm90bzM="));
    descriptor = pbr::FileDescriptor.FromGeneratedCode(descriptorData,
        new pbr::FileDescriptor[] { },
        new pbr::GeneratedClrTypeInfo(null, new pbr::GeneratedClrTypeInfo[] {
          new pbr::GeneratedClrTypeInfo(typeof(global::TransactionHeader), global::TransactionHeader.Parser, new[]{ "BatcherPublicKey", "Dependencies", "FamilyName", "FamilyVersion", "Inputs", "Nonce", "Outputs", "PayloadSha512", "SignerPublicKey" }, null, null, null),
          new pbr::GeneratedClrTypeInfo(typeof(global::Transaction), global::Transaction.Parser, new[]{ "Header", "HeaderSignature", "Payload" }, null, null, null),
          new pbr::GeneratedClrTypeInfo(typeof(global::TransactionList), global::TransactionList.Parser, new[]{ "Transactions" }, null, null, null)
        }));
  }
  #endregion

}
#region Messages
public sealed partial class TransactionHeader : pb::IMessage<TransactionHeader> {
  private static readonly pb::MessageParser<TransactionHeader> _parser = new pb::MessageParser<TransactionHeader>(() => new TransactionHeader());
  private pb::UnknownFieldSet _unknownFields;
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public static pb::MessageParser<TransactionHeader> Parser { get { return _parser; } }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public static pbr::MessageDescriptor Descriptor {
    get { return global::TransactionReflection.Descriptor.MessageTypes[0]; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  pbr::MessageDescriptor pb::IMessage.Descriptor {
    get { return Descriptor; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public TransactionHeader() {
    OnConstruction();
  }

  partial void OnConstruction();

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public TransactionHeader(TransactionHeader other) : this() {
    batcherPublicKey_ = other.batcherPublicKey_;
    dependencies_ = other.dependencies_.Clone();
    familyName_ = other.familyName_;
    familyVersion_ = other.familyVersion_;
    inputs_ = other.inputs_.Clone();
    nonce_ = other.nonce_;
    outputs_ = other.outputs_.Clone();
    payloadSha512_ = other.payloadSha512_;
    signerPublicKey_ = other.signerPublicKey_;
    _unknownFields = pb::UnknownFieldSet.Clone(other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public TransactionHeader Clone() {
    return new TransactionHeader(this);
  }

  /// <summary>Field number for the "batcher_public_key" field.</summary>
  public const int BatcherPublicKeyFieldNumber = 1;
  private string batcherPublicKey_ = "";
  /// <summary>
  /// Public key for the client who added this transaction to a batch
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public string BatcherPublicKey {
    get { return batcherPublicKey_; }
    set {
      batcherPublicKey_ = pb::ProtoPreconditions.CheckNotNull(value, "value");
    }
  }

  /// <summary>Field number for the "dependencies" field.</summary>
  public const int DependenciesFieldNumber = 2;
  private static readonly pb::FieldCodec<string> _repeated_dependencies_codec
      = pb::FieldCodec.ForString(18);
  private readonly pbc::RepeatedField<string> dependencies_ = new pbc::RepeatedField<string>();
  /// <summary>
  /// A list of transaction signatures that describe the transactions that
  /// must be processed before this transaction can be valid
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public pbc::RepeatedField<string> Dependencies {
    get { return dependencies_; }
  }

  /// <summary>Field number for the "family_name" field.</summary>
  public const int FamilyNameFieldNumber = 3;
  private string familyName_ = "";
  /// <summary>
  /// The family name correlates to the transaction processor's family name
  /// that this transaction can be processed on, for example 'intkey'
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public string FamilyName {
    get { return familyName_; }
    set {
      familyName_ = pb::ProtoPreconditions.CheckNotNull(value, "value");
    }
  }

  /// <summary>Field number for the "family_version" field.</summary>
  public const int FamilyVersionFieldNumber = 4;
  private string familyVersion_ = "";
  /// <summary>
  /// The family version correlates to the transaction processor's family
  /// version that this transaction can be processed on, for example "1.0"
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public string FamilyVersion {
    get { return familyVersion_; }
    set {
      familyVersion_ = pb::ProtoPreconditions.CheckNotNull(value, "value");
    }
  }

  /// <summary>Field number for the "inputs" field.</summary>
  public const int InputsFieldNumber = 5;
  private static readonly pb::FieldCodec<string> _repeated_inputs_codec
      = pb::FieldCodec.ForString(42);
  private readonly pbc::RepeatedField<string> inputs_ = new pbc::RepeatedField<string>();
  /// <summary>
  /// A list of addresses that are given to the context manager and control
  /// what addresses the transaction processor is allowed to read from.
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public pbc::RepeatedField<string> Inputs {
    get { return inputs_; }
  }

  /// <summary>Field number for the "nonce" field.</summary>
  public const int NonceFieldNumber = 6;
  private string nonce_ = "";
  /// <summary>
  /// A random string that provides uniqueness for transactions with
  /// otherwise identical fields.
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public string Nonce {
    get { return nonce_; }
    set {
      nonce_ = pb::ProtoPreconditions.CheckNotNull(value, "value");
    }
  }

  /// <summary>Field number for the "outputs" field.</summary>
  public const int OutputsFieldNumber = 7;
  private static readonly pb::FieldCodec<string> _repeated_outputs_codec
      = pb::FieldCodec.ForString(58);
  private readonly pbc::RepeatedField<string> outputs_ = new pbc::RepeatedField<string>();
  /// <summary>
  /// A list of addresses that are given to the context manager and control
  /// what addresses the transaction processor is allowed to write to.
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public pbc::RepeatedField<string> Outputs {
    get { return outputs_; }
  }

  /// <summary>Field number for the "payload_sha512" field.</summary>
  public const int PayloadSha512FieldNumber = 9;
  private string payloadSha512_ = "";
  /// <summary>
  ///The sha512 hash of the encoded payload
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public string PayloadSha512 {
    get { return payloadSha512_; }
    set {
      payloadSha512_ = pb::ProtoPreconditions.CheckNotNull(value, "value");
    }
  }

  /// <summary>Field number for the "signer_public_key" field.</summary>
  public const int SignerPublicKeyFieldNumber = 10;
  private string signerPublicKey_ = "";
  /// <summary>
  /// Public key for the client that signed the TransactionHeader
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public string SignerPublicKey {
    get { return signerPublicKey_; }
    set {
      signerPublicKey_ = pb::ProtoPreconditions.CheckNotNull(value, "value");
    }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override bool Equals(object other) {
    return Equals(other as TransactionHeader);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public bool Equals(TransactionHeader other) {
    if (ReferenceEquals(other, null)) {
      return false;
    }
    if (ReferenceEquals(other, this)) {
      return true;
    }
    if (BatcherPublicKey != other.BatcherPublicKey) return false;
    if(!dependencies_.Equals(other.dependencies_)) return false;
    if (FamilyName != other.FamilyName) return false;
    if (FamilyVersion != other.FamilyVersion) return false;
    if(!inputs_.Equals(other.inputs_)) return false;
    if (Nonce != other.Nonce) return false;
    if(!outputs_.Equals(other.outputs_)) return false;
    if (PayloadSha512 != other.PayloadSha512) return false;
    if (SignerPublicKey != other.SignerPublicKey) return false;
    return Equals(_unknownFields, other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override int GetHashCode() {
    int hash = 1;
    if (BatcherPublicKey.Length != 0) hash ^= BatcherPublicKey.GetHashCode();
    hash ^= dependencies_.GetHashCode();
    if (FamilyName.Length != 0) hash ^= FamilyName.GetHashCode();
    if (FamilyVersion.Length != 0) hash ^= FamilyVersion.GetHashCode();
    hash ^= inputs_.GetHashCode();
    if (Nonce.Length != 0) hash ^= Nonce.GetHashCode();
    hash ^= outputs_.GetHashCode();
    if (PayloadSha512.Length != 0) hash ^= PayloadSha512.GetHashCode();
    if (SignerPublicKey.Length != 0) hash ^= SignerPublicKey.GetHashCode();
    if (_unknownFields != null) {
      hash ^= _unknownFields.GetHashCode();
    }
    return hash;
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override string ToString() {
    return pb::JsonFormatter.ToDiagnosticString(this);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public void WriteTo(pb::CodedOutputStream output) {
    if (BatcherPublicKey.Length != 0) {
      output.WriteRawTag(10);
      output.WriteString(BatcherPublicKey);
    }
    dependencies_.WriteTo(output, _repeated_dependencies_codec);
    if (FamilyName.Length != 0) {
      output.WriteRawTag(26);
      output.WriteString(FamilyName);
    }
    if (FamilyVersion.Length != 0) {
      output.WriteRawTag(34);
      output.WriteString(FamilyVersion);
    }
    inputs_.WriteTo(output, _repeated_inputs_codec);
    if (Nonce.Length != 0) {
      output.WriteRawTag(50);
      output.WriteString(Nonce);
    }
    outputs_.WriteTo(output, _repeated_outputs_codec);
    if (PayloadSha512.Length != 0) {
      output.WriteRawTag(74);
      output.WriteString(PayloadSha512);
    }
    if (SignerPublicKey.Length != 0) {
      output.WriteRawTag(82);
      output.WriteString(SignerPublicKey);
    }
    if (_unknownFields != null) {
      _unknownFields.WriteTo(output);
    }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public int CalculateSize() {
    int size = 0;
    if (BatcherPublicKey.Length != 0) {
      size += 1 + pb::CodedOutputStream.ComputeStringSize(BatcherPublicKey);
    }
    size += dependencies_.CalculateSize(_repeated_dependencies_codec);
    if (FamilyName.Length != 0) {
      size += 1 + pb::CodedOutputStream.ComputeStringSize(FamilyName);
    }
    if (FamilyVersion.Length != 0) {
      size += 1 + pb::CodedOutputStream.ComputeStringSize(FamilyVersion);
    }
    size += inputs_.CalculateSize(_repeated_inputs_codec);
    if (Nonce.Length != 0) {
      size += 1 + pb::CodedOutputStream.ComputeStringSize(Nonce);
    }
    size += outputs_.CalculateSize(_repeated_outputs_codec);
    if (PayloadSha512.Length != 0) {
      size += 1 + pb::CodedOutputStream.ComputeStringSize(PayloadSha512);
    }
    if (SignerPublicKey.Length != 0) {
      size += 1 + pb::CodedOutputStream.ComputeStringSize(SignerPublicKey);
    }
    if (_unknownFields != null) {
      size += _unknownFields.CalculateSize();
    }
    return size;
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public void MergeFrom(TransactionHeader other) {
    if (other == null) {
      return;
    }
    if (other.BatcherPublicKey.Length != 0) {
      BatcherPublicKey = other.BatcherPublicKey;
    }
    dependencies_.Add(other.dependencies_);
    if (other.FamilyName.Length != 0) {
      FamilyName = other.FamilyName;
    }
    if (other.FamilyVersion.Length != 0) {
      FamilyVersion = other.FamilyVersion;
    }
    inputs_.Add(other.inputs_);
    if (other.Nonce.Length != 0) {
      Nonce = other.Nonce;
    }
    outputs_.Add(other.outputs_);
    if (other.PayloadSha512.Length != 0) {
      PayloadSha512 = other.PayloadSha512;
    }
    if (other.SignerPublicKey.Length != 0) {
      SignerPublicKey = other.SignerPublicKey;
    }
    _unknownFields = pb::UnknownFieldSet.MergeFrom(_unknownFields, other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public void MergeFrom(pb::CodedInputStream input) {
    uint tag;
    while ((tag = input.ReadTag()) != 0) {
      switch(tag) {
        default:
          _unknownFields = pb::UnknownFieldSet.MergeFieldFrom(_unknownFields, input);
          break;
        case 10: {
          BatcherPublicKey = input.ReadString();
          break;
        }
        case 18: {
          dependencies_.AddEntriesFrom(input, _repeated_dependencies_codec);
          break;
        }
        case 26: {
          FamilyName = input.ReadString();
          break;
        }
        case 34: {
          FamilyVersion = input.ReadString();
          break;
        }
        case 42: {
          inputs_.AddEntriesFrom(input, _repeated_inputs_codec);
          break;
        }
        case 50: {
          Nonce = input.ReadString();
          break;
        }
        case 58: {
          outputs_.AddEntriesFrom(input, _repeated_outputs_codec);
          break;
        }
        case 74: {
          PayloadSha512 = input.ReadString();
          break;
        }
        case 82: {
          SignerPublicKey = input.ReadString();
          break;
        }
      }
    }
  }

}

public sealed partial class Transaction : pb::IMessage<Transaction> {
  private static readonly pb::MessageParser<Transaction> _parser = new pb::MessageParser<Transaction>(() => new Transaction());
  private pb::UnknownFieldSet _unknownFields;
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public static pb::MessageParser<Transaction> Parser { get { return _parser; } }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public static pbr::MessageDescriptor Descriptor {
    get { return global::TransactionReflection.Descriptor.MessageTypes[1]; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  pbr::MessageDescriptor pb::IMessage.Descriptor {
    get { return Descriptor; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public Transaction() {
    OnConstruction();
  }

  partial void OnConstruction();

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public Transaction(Transaction other) : this() {
    header_ = other.header_;
    headerSignature_ = other.headerSignature_;
    payload_ = other.payload_;
    _unknownFields = pb::UnknownFieldSet.Clone(other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public Transaction Clone() {
    return new Transaction(this);
  }

  /// <summary>Field number for the "header" field.</summary>
  public const int HeaderFieldNumber = 1;
  private pb::ByteString header_ = pb::ByteString.Empty;
  /// <summary>
  /// The serialized version of the TransactionHeader
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public pb::ByteString Header {
    get { return header_; }
    set {
      header_ = pb::ProtoPreconditions.CheckNotNull(value, "value");
    }
  }

  /// <summary>Field number for the "header_signature" field.</summary>
  public const int HeaderSignatureFieldNumber = 2;
  private string headerSignature_ = "";
  /// <summary>
  /// The signature derived from signing the header
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public string HeaderSignature {
    get { return headerSignature_; }
    set {
      headerSignature_ = pb::ProtoPreconditions.CheckNotNull(value, "value");
    }
  }

  /// <summary>Field number for the "payload" field.</summary>
  public const int PayloadFieldNumber = 3;
  private pb::ByteString payload_ = pb::ByteString.Empty;
  /// <summary>
  /// The payload is the encoded family specific information of the
  /// transaction. Example cbor({'Verb': verb, 'Name': name,'Value': value})
  /// </summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public pb::ByteString Payload {
    get { return payload_; }
    set {
      payload_ = pb::ProtoPreconditions.CheckNotNull(value, "value");
    }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override bool Equals(object other) {
    return Equals(other as Transaction);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public bool Equals(Transaction other) {
    if (ReferenceEquals(other, null)) {
      return false;
    }
    if (ReferenceEquals(other, this)) {
      return true;
    }
    if (Header != other.Header) return false;
    if (HeaderSignature != other.HeaderSignature) return false;
    if (Payload != other.Payload) return false;
    return Equals(_unknownFields, other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override int GetHashCode() {
    int hash = 1;
    if (Header.Length != 0) hash ^= Header.GetHashCode();
    if (HeaderSignature.Length != 0) hash ^= HeaderSignature.GetHashCode();
    if (Payload.Length != 0) hash ^= Payload.GetHashCode();
    if (_unknownFields != null) {
      hash ^= _unknownFields.GetHashCode();
    }
    return hash;
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override string ToString() {
    return pb::JsonFormatter.ToDiagnosticString(this);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public void WriteTo(pb::CodedOutputStream output) {
    if (Header.Length != 0) {
      output.WriteRawTag(10);
      output.WriteBytes(Header);
    }
    if (HeaderSignature.Length != 0) {
      output.WriteRawTag(18);
      output.WriteString(HeaderSignature);
    }
    if (Payload.Length != 0) {
      output.WriteRawTag(26);
      output.WriteBytes(Payload);
    }
    if (_unknownFields != null) {
      _unknownFields.WriteTo(output);
    }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public int CalculateSize() {
    int size = 0;
    if (Header.Length != 0) {
      size += 1 + pb::CodedOutputStream.ComputeBytesSize(Header);
    }
    if (HeaderSignature.Length != 0) {
      size += 1 + pb::CodedOutputStream.ComputeStringSize(HeaderSignature);
    }
    if (Payload.Length != 0) {
      size += 1 + pb::CodedOutputStream.ComputeBytesSize(Payload);
    }
    if (_unknownFields != null) {
      size += _unknownFields.CalculateSize();
    }
    return size;
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public void MergeFrom(Transaction other) {
    if (other == null) {
      return;
    }
    if (other.Header.Length != 0) {
      Header = other.Header;
    }
    if (other.HeaderSignature.Length != 0) {
      HeaderSignature = other.HeaderSignature;
    }
    if (other.Payload.Length != 0) {
      Payload = other.Payload;
    }
    _unknownFields = pb::UnknownFieldSet.MergeFrom(_unknownFields, other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public void MergeFrom(pb::CodedInputStream input) {
    uint tag;
    while ((tag = input.ReadTag()) != 0) {
      switch(tag) {
        default:
          _unknownFields = pb::UnknownFieldSet.MergeFieldFrom(_unknownFields, input);
          break;
        case 10: {
          Header = input.ReadBytes();
          break;
        }
        case 18: {
          HeaderSignature = input.ReadString();
          break;
        }
        case 26: {
          Payload = input.ReadBytes();
          break;
        }
      }
    }
  }

}

/// <summary>
/// A simple list of transactions that needs to be serialized before
/// it can be transmitted to a batcher.
/// </summary>
public sealed partial class TransactionList : pb::IMessage<TransactionList> {
  private static readonly pb::MessageParser<TransactionList> _parser = new pb::MessageParser<TransactionList>(() => new TransactionList());
  private pb::UnknownFieldSet _unknownFields;
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public static pb::MessageParser<TransactionList> Parser { get { return _parser; } }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public static pbr::MessageDescriptor Descriptor {
    get { return global::TransactionReflection.Descriptor.MessageTypes[2]; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  pbr::MessageDescriptor pb::IMessage.Descriptor {
    get { return Descriptor; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public TransactionList() {
    OnConstruction();
  }

  partial void OnConstruction();

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public TransactionList(TransactionList other) : this() {
    transactions_ = other.transactions_.Clone();
    _unknownFields = pb::UnknownFieldSet.Clone(other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public TransactionList Clone() {
    return new TransactionList(this);
  }

  /// <summary>Field number for the "transactions" field.</summary>
  public const int TransactionsFieldNumber = 1;
  private static readonly pb::FieldCodec<global::Transaction> _repeated_transactions_codec
      = pb::FieldCodec.ForMessage(10, global::Transaction.Parser);
  private readonly pbc::RepeatedField<global::Transaction> transactions_ = new pbc::RepeatedField<global::Transaction>();
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public pbc::RepeatedField<global::Transaction> Transactions {
    get { return transactions_; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override bool Equals(object other) {
    return Equals(other as TransactionList);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public bool Equals(TransactionList other) {
    if (ReferenceEquals(other, null)) {
      return false;
    }
    if (ReferenceEquals(other, this)) {
      return true;
    }
    if(!transactions_.Equals(other.transactions_)) return false;
    return Equals(_unknownFields, other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override int GetHashCode() {
    int hash = 1;
    hash ^= transactions_.GetHashCode();
    if (_unknownFields != null) {
      hash ^= _unknownFields.GetHashCode();
    }
    return hash;
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override string ToString() {
    return pb::JsonFormatter.ToDiagnosticString(this);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public void WriteTo(pb::CodedOutputStream output) {
    transactions_.WriteTo(output, _repeated_transactions_codec);
    if (_unknownFields != null) {
      _unknownFields.WriteTo(output);
    }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public int CalculateSize() {
    int size = 0;
    size += transactions_.CalculateSize(_repeated_transactions_codec);
    if (_unknownFields != null) {
      size += _unknownFields.CalculateSize();
    }
    return size;
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public void MergeFrom(TransactionList other) {
    if (other == null) {
      return;
    }
    transactions_.Add(other.transactions_);
    _unknownFields = pb::UnknownFieldSet.MergeFrom(_unknownFields, other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public void MergeFrom(pb::CodedInputStream input) {
    uint tag;
    while ((tag = input.ReadTag()) != 0) {
      switch(tag) {
        default:
          _unknownFields = pb::UnknownFieldSet.MergeFieldFrom(_unknownFields, input);
          break;
        case 10: {
          transactions_.AddEntriesFrom(input, _repeated_transactions_codec);
          break;
        }
      }
    }
  }

}

#endregion


#endregion Designer generated code

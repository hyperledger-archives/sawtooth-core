// <auto-generated>
//     Generated by the protocol buffer compiler.  DO NOT EDIT!
//     source: client_peers.proto
// </auto-generated>
#pragma warning disable 1591, 0612, 3021
#region Designer generated code

using pb = global::Google.Protobuf;
using pbc = global::Google.Protobuf.Collections;
using pbr = global::Google.Protobuf.Reflection;
using scg = global::System.Collections.Generic;
/// <summary>Holder for reflection information generated from client_peers.proto</summary>
public static partial class ClientPeersReflection {

  #region Descriptor
  /// <summary>File descriptor for client_peers.proto</summary>
  public static pbr::FileDescriptor Descriptor {
    get { return descriptor; }
  }
  private static pbr::FileDescriptor descriptor;

  static ClientPeersReflection() {
    byte[] descriptorData = global::System.Convert.FromBase64String(
        string.Concat(
          "ChJjbGllbnRfcGVlcnMucHJvdG8iFwoVQ2xpZW50UGVlcnNHZXRSZXF1ZXN0",
          "IoYBChZDbGllbnRQZWVyc0dldFJlc3BvbnNlEi4KBnN0YXR1cxgBIAEoDjIe",
          "LkNsaWVudFBlZXJzR2V0UmVzcG9uc2UuU3RhdHVzEg0KBXBlZXJzGAIgAygJ",
          "Ii0KBlN0YXR1cxIQCgxTVEFUVVNfVU5TRVQQABIGCgJPSxABEgkKBUVSUk9S",
          "EAJCJgoVc2F3dG9vdGguc2RrLnByb3RvYnVmUAFaC2NsaWVudF9wZWVyYgZw",
          "cm90bzM="));
    descriptor = pbr::FileDescriptor.FromGeneratedCode(descriptorData,
        new pbr::FileDescriptor[] { },
        new pbr::GeneratedClrTypeInfo(null, new pbr::GeneratedClrTypeInfo[] {
          new pbr::GeneratedClrTypeInfo(typeof(global::ClientPeersGetRequest), global::ClientPeersGetRequest.Parser, null, null, null, null),
          new pbr::GeneratedClrTypeInfo(typeof(global::ClientPeersGetResponse), global::ClientPeersGetResponse.Parser, new[]{ "Status", "Peers" }, null, new[]{ typeof(global::ClientPeersGetResponse.Types.Status) }, null)
        }));
  }
  #endregion

}
#region Messages
public sealed partial class ClientPeersGetRequest : pb::IMessage<ClientPeersGetRequest> {
  private static readonly pb::MessageParser<ClientPeersGetRequest> _parser = new pb::MessageParser<ClientPeersGetRequest>(() => new ClientPeersGetRequest());
  private pb::UnknownFieldSet _unknownFields;
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public static pb::MessageParser<ClientPeersGetRequest> Parser { get { return _parser; } }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public static pbr::MessageDescriptor Descriptor {
    get { return global::ClientPeersReflection.Descriptor.MessageTypes[0]; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  pbr::MessageDescriptor pb::IMessage.Descriptor {
    get { return Descriptor; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public ClientPeersGetRequest() {
    OnConstruction();
  }

  partial void OnConstruction();

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public ClientPeersGetRequest(ClientPeersGetRequest other) : this() {
    _unknownFields = pb::UnknownFieldSet.Clone(other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public ClientPeersGetRequest Clone() {
    return new ClientPeersGetRequest(this);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override bool Equals(object other) {
    return Equals(other as ClientPeersGetRequest);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public bool Equals(ClientPeersGetRequest other) {
    if (ReferenceEquals(other, null)) {
      return false;
    }
    if (ReferenceEquals(other, this)) {
      return true;
    }
    return Equals(_unknownFields, other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override int GetHashCode() {
    int hash = 1;
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
    if (_unknownFields != null) {
      _unknownFields.WriteTo(output);
    }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public int CalculateSize() {
    int size = 0;
    if (_unknownFields != null) {
      size += _unknownFields.CalculateSize();
    }
    return size;
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public void MergeFrom(ClientPeersGetRequest other) {
    if (other == null) {
      return;
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
      }
    }
  }

}

public sealed partial class ClientPeersGetResponse : pb::IMessage<ClientPeersGetResponse> {
  private static readonly pb::MessageParser<ClientPeersGetResponse> _parser = new pb::MessageParser<ClientPeersGetResponse>(() => new ClientPeersGetResponse());
  private pb::UnknownFieldSet _unknownFields;
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public static pb::MessageParser<ClientPeersGetResponse> Parser { get { return _parser; } }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public static pbr::MessageDescriptor Descriptor {
    get { return global::ClientPeersReflection.Descriptor.MessageTypes[1]; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  pbr::MessageDescriptor pb::IMessage.Descriptor {
    get { return Descriptor; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public ClientPeersGetResponse() {
    OnConstruction();
  }

  partial void OnConstruction();

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public ClientPeersGetResponse(ClientPeersGetResponse other) : this() {
    status_ = other.status_;
    peers_ = other.peers_.Clone();
    _unknownFields = pb::UnknownFieldSet.Clone(other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public ClientPeersGetResponse Clone() {
    return new ClientPeersGetResponse(this);
  }

  /// <summary>Field number for the "status" field.</summary>
  public const int StatusFieldNumber = 1;
  private global::ClientPeersGetResponse.Types.Status status_ = 0;
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public global::ClientPeersGetResponse.Types.Status Status {
    get { return status_; }
    set {
      status_ = value;
    }
  }

  /// <summary>Field number for the "peers" field.</summary>
  public const int PeersFieldNumber = 2;
  private static readonly pb::FieldCodec<string> _repeated_peers_codec
      = pb::FieldCodec.ForString(18);
  private readonly pbc::RepeatedField<string> peers_ = new pbc::RepeatedField<string>();
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public pbc::RepeatedField<string> Peers {
    get { return peers_; }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override bool Equals(object other) {
    return Equals(other as ClientPeersGetResponse);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public bool Equals(ClientPeersGetResponse other) {
    if (ReferenceEquals(other, null)) {
      return false;
    }
    if (ReferenceEquals(other, this)) {
      return true;
    }
    if (Status != other.Status) return false;
    if(!peers_.Equals(other.peers_)) return false;
    return Equals(_unknownFields, other._unknownFields);
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public override int GetHashCode() {
    int hash = 1;
    if (Status != 0) hash ^= Status.GetHashCode();
    hash ^= peers_.GetHashCode();
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
    if (Status != 0) {
      output.WriteRawTag(8);
      output.WriteEnum((int) Status);
    }
    peers_.WriteTo(output, _repeated_peers_codec);
    if (_unknownFields != null) {
      _unknownFields.WriteTo(output);
    }
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public int CalculateSize() {
    int size = 0;
    if (Status != 0) {
      size += 1 + pb::CodedOutputStream.ComputeEnumSize((int) Status);
    }
    size += peers_.CalculateSize(_repeated_peers_codec);
    if (_unknownFields != null) {
      size += _unknownFields.CalculateSize();
    }
    return size;
  }

  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public void MergeFrom(ClientPeersGetResponse other) {
    if (other == null) {
      return;
    }
    if (other.Status != 0) {
      Status = other.Status;
    }
    peers_.Add(other.peers_);
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
        case 8: {
          status_ = (global::ClientPeersGetResponse.Types.Status) input.ReadEnum();
          break;
        }
        case 18: {
          peers_.AddEntriesFrom(input, _repeated_peers_codec);
          break;
        }
      }
    }
  }

  #region Nested types
  /// <summary>Container for nested types declared in the ClientPeersGetResponse message type.</summary>
  [global::System.Diagnostics.DebuggerNonUserCodeAttribute]
  public static partial class Types {
    public enum Status {
      [pbr::OriginalName("STATUS_UNSET")] Unset = 0,
      [pbr::OriginalName("OK")] Ok = 1,
      [pbr::OriginalName("ERROR")] Error = 2,
    }

  }
  #endregion

}

#endregion


#endregion Designer generated code

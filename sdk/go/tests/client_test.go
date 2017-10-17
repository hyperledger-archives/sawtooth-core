package tests

import (
    "encoding/hex"
    "testing"
    . "sawtooth_sdk/client"
)

var (
  data = []byte{0x01, 0x02, 0x03}
  PEMSTR = `-----BEGIN EC PRIVATE KEY-----
MHQCAQEEIISGREvlByLRnbhovpK8wSd5hnymtY8hdQCOvZQ473CpoAcGBSuBBAAK
oUQDQgAEWC6TyM1jpYu3f/GGIuktDk4nM1qyOf9PEPHkRkN8zK2HxxNwDi+yN3hR
8Ag+VeTwbRRZOlBdFBsgPxz3/864hw==
-----END EC PRIVATE KEY-----
`
  PEMSTRPRIV = "8486444be50722d19db868be92bcc12779867ca6b58f2175008ebd9438ef70a9"
  ENCPEM = `-----BEGIN EC PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: AES-128-CBC,23CDF282F2217A9334A2413D78DAE04C

PQy89wdLsayP/FG68wgmL1EdlI3S5pN8ibCFrnp5OAtVNrYUD/TH9DMYVmRCNUB4
e+vXoQzd1IysjoFpV21zajSAxCmcbU4CGCDEea3GPwirOSE0ZjPHPp15IkRuGFYm
L/8e9mXvEQPAmBC0NMiltnk4/26iN7hB1QxSQQwy/Zc=
-----END EC PRIVATE KEY-----
`
  ENCPEMPRIV = "2cc32bc33935a5dbad8118abc63dfb627bb91a98d5e6310f5d60f5d65f6adb2f"
  PEMPUBSTR = "03582e93c8cd63a58bb77ff18622e92d0e4e27335ab239ff4f10f1e446437cccad"
  ENCPEMPUB = "0257510b4718fd79b21dee3173ffb48ab9a668a35a377be7b7dc432243a940c510"
  WIFSTR = "5J7bEeWs14sKkz7yVHfVc2FXKfBe6Hb5oNZxxTKqKZCgjbDTuUj"
  PUBSTR = "035e1de3048a62f9f478440a22fd7655b80f0aac997be963b119ac54b3bfdea3b7"
  SIGSTR = "0062bc154dca72472e66062c4539c8befb2680d79d59b3cc539dd182ff36072b199adc1118db5fc1884d50cdec9d31a2356af03175439ccb841c7b0e3ae83297"
  ENCDED="0ab40a0aca020a423033356531646533303438613632663966343738343430613232666437363535623830663061616339393762653936336231313961633534623362666465613362371280013064366530643165323133346462353833316138313964323364376132333835383836613266633063303739663837613630613130323635396237373835613532626364363037333537396537376532663964333936323136393139643134363264666430646538646136373564336233633830333066303632663032353634128001343631313764356234303934393865663265653537663061616338633932623164393831353238636561343731613230633634333963333434666230616235613334363262363830393961326665643734303532343134653034386362306632303032356266626636333736353636313365386464643164666430313164323112800137313265623534646435633965653837616561656633346164646338623765626664353231393865663165356162656466306666306132373863376262633961376439343331643531633636663236613032366336373637333162316166396335363166396131663066623065373530366464656666396162373063626663331aaf030aa4020a423033356531646533303438613632663966343738343430613232666437363535623830663061616339393762653936336231313961633534623362666465613362371a0361626322033132332a0364656632033132333a036465664a80013237383634636335323139613935316137613665353262386338646464663639383164303938646131363538643936323538633837306232633838646662636235313834316165613137326132386261666136613739373331313635353834363737303636303435633935396564306639393239363838643034646566633239524230333565316465333034386136326639663437383434306132326664373635356238306630616163393937626539363362313139616335346233626664656133623712800130643665306431653231333464623538333161383139643233643761323338353838366132666330633037396638376136306131303236353962373738356135326263643630373335373965373765326639643339363231363931396431343632646664306465386461363735643362336338303330663036326630323536341a030102031aaf030aa4020a423033356531646533303438613632663966343738343430613232666437363535623830663061616339393762653936336231313961633534623362666465613362371a0361626322033132332a0364656632033435363a036768694a80013237383634636335323139613935316137613665353262386338646464663639383164303938646131363538643936323538633837306232633838646662636235313834316165613137326132386261666136613739373331313635353834363737303636303435633935396564306639393239363838643034646566633239524230333565316465333034386136326639663437383434306132326664373635356238306630616163393937626539363362313139616335346233626664656133623712800134363131376435623430393439386566326565353766306161633863393262316439383135323863656134373161323063363433396333343466623061623561333436326236383039396132666564373430353234313465303438636230663230303235626662663633373635363631336538646464316466643031316432311a03010203"
)

func TestSigning(t *testing.T) {
    priv := GenPrivKey()
    pub := GenPubKey(priv)
    sig := Sign(data, priv)
    if !Verify(data, sig, pub) {
        t.Error(
            "Couldn't verify generated signature",
            priv, pub, sig,
        )
    }
}

func TestEncoding(t *testing.T) {
    priv, err := WifToPriv(WIFSTR)
    if err != nil {
        t.Error("Failed to load WIF key")
    }
    if PrivToWif(priv) != WIFSTR {
        t.Error("Private key is different after encoding/decoding")
    }
    if hex.EncodeToString(GenPubKey(priv)) != PUBSTR {
        t.Error("Public key doesn't match expected. Got", GenPubKey(priv))
    }
    sigstr := hex.EncodeToString(Sign(data, priv))
    if sigstr != SIGSTR {
        t.Error("Signature doesn't match expected. Got", sigstr)
    }
}

func TestPemLoader(t *testing.T) {
    // Load the keys
    priv, err := PemToPriv(PEMSTR, "")
    if err != nil {
        t.Error("Failed to load unencrypted PEM key")
    }
    epriv, err := PemToPriv(ENCPEM, "password")
    if err != nil {
        t.Error("Failed to load encrypted PEM key")
    }
    // Test that they match expected
    if hex.EncodeToString(priv) != PEMSTRPRIV {
        t.Error("Failed to parse unencrypted PEM key")
    }
    if hex.EncodeToString(epriv) != ENCPEMPRIV {
        t.Error("Failed to parse encrypted PEM key")
    }
    // Test that the correct public keys are generated
    pub := hex.EncodeToString(GenPubKey(priv))
    epub := hex.EncodeToString(GenPubKey(epriv))
    if pub != PEMPUBSTR {
      t.Error("Failed to generate correct public key from unencrypted PEM key")
    }
    if epub != ENCPEMPUB {
      t.Error("Failed to generate correct public key from encrypted PEM key")
    }
}

func TestEncoder(t *testing.T) {
    priv, _ := WifToPriv(WIFSTR)

    encoder := NewEncoder(priv, TransactionParams{
        FamilyName: "abc",
        FamilyVersion: "123",
        Inputs: []string{"def"},
    })

    txn1 := encoder.NewTransaction(data, TransactionParams{
        Nonce: "123",
        Outputs: []string{"def"},
    })

    pubstr := hex.EncodeToString(GenPubKey(priv))
    txn2 := encoder.NewTransaction(data, TransactionParams{
        Nonce: "456",
        Outputs: []string{"ghi"},
        BatcherPubkey: pubstr,
    })

    // Test serialization
    txns, err := ParseTransactions(SerializeTransactions([]*Transaction{txn1, txn2}))
    if err != nil {
        t.Error(err)
    }

    batch := encoder.NewBatch(txns)

    // Test serialization
    batches, err := ParseBatches(SerializeBatches([]*Batch{batch}))
    if err != nil {
        t.Error(err)
    }
    data := SerializeBatches(batches)
    datastr := hex.EncodeToString(data)

    expected := ENCDED

    if datastr != expected {
        t.Error("Did not correctly encode batch. Got", datastr)
    }
}

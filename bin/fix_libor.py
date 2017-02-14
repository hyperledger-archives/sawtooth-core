from sawtooth_bond.updates.libor import LIBORObject
from sawtooth_signing import pbct_nativerecover as signing
import yaml

def create_libor(dct):
    return LIBORObject(
        date=dct['Date'],
        rates=dct['Rates'],
        public_key=None
    )

def sign_libor(libor, priv_key):
    libor.sign_object(priv_key)

def to_file(filename, updates):
    dcts = []
    for update in updates:
        d = update.dump()
        d['UpdateType'] = 'CreateLIBOR'
        dcts.append(d)

    output = yaml.dump({
        'Transactions': [ {
            'Updates': dcts
        } ]
    }, default_flow_style=False) 
                
    with open(filename, "w") as fd:
        fd.write(output)

private_key = "5K2Q6hh28DcmKCAnxFc72pafZTmvik9mQde8Fb4MtJfDtVwp4Bx"
public_key = signing.generate_pubkey(private_key)
addr = signing.generate_identifier(public_key)

with open("/project/sawtooth-core/extensions/bond/data/libor.yaml") as fd:
    libor_data = yaml.load(fd.read())

updates = libor_data['Transactions'][0]['Updates']

libors = []
for update in updates:
    lo = create_libor(update)
    print(lo.dump())
    sign_libor(lo, private_key)
    print(lo.dump())
    libors.append(lo)

to_file("/project/sawtooth-core/extensions/bond/data/libor_new.yaml", libors)

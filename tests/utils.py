
import hashlib
import random
import string
from journal.consensus.poet.poet_enclave_simulator \
    import poet_enclave_simulator as poet


class AttrDict(dict):
    """ A simple mocking class.
     """
    def __init__(self, **kwargs):
        dict.__init__(self, *(), **kwargs)

    def __getattr__(self, name):
        return self[name]


def generate_certs(count):
    out = []
    for i in range(0, count):
        out.append(AttrDict(**{
            "identifier": random_name(poet.IDENTIFIER_LENGTH),
            "duration": 2,
            "local_mean": 1
        }))
    return out


def random_name(length=16):
    return ''.join(
        random.SystemRandom().choice(string.ascii_uppercase + string.digits)
        for _ in range(length))


def generate_txn_ids(count):
    out = []
    hasher = hashlib.sha256()
    for i in range(0, count):
        name = random_name(poet.IDENTIFIER_LENGTH)
        hasher.update(name)
        out.append(name)
    return out, hasher.hexdigest()

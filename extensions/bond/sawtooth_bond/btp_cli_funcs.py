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

import os
import hashlib
import pybitcointools
import yaml

from gossip.common import dict2cbor
from sawtooth.exceptions import ClientException
from sawtooth.client import UpdateBatch
from sawtooth_bond.bond_client import BondClient
from sawtooth_bond.bond_utils import float_to_bondprice
from sawtooth_bond.btp_cli_utils import ListWriter
from sawtooth_bond.btp_cli_utils import ShowWriter
from sawtooth_bond.btp_cli_utils import save_config
from sawtooth_bond.btp_cli_utils import change_config
from sawtooth_bond.btp_cli_utils import try_get_then_lookup
from sawtooth_bond.btp_cli_utils import change_wif_and_addr_filename


def do_init(args, config):
    username = config.get('DEFAULT', 'username')
    if args.username is not None:
        if len(args.username) < 3 or len(args.username) > 16:
            raise ClientException(
                "username must be between 3 and 16 characters")
        username = args.username
        config.set('DEFAULT', 'username', username)
        print "set username: {}".format(username)
    else:
        print "Username: {}".format(username)

    http_url = config.get('DEFAULT', 'url')
    if args.url is not None:
        http_url = args.url
        config.set('DEFAULT', 'url', http_url)
        print "set url to {}".format(http_url)
    else:
        print "Validator url: {}".format(http_url)

    save_config(config)

    wif_filename = config.get('DEFAULT', 'key_file')
    if wif_filename.endswith(".wif"):
        addr_filename = wif_filename[0:-len(".wif")] + ".addr"
    else:
        addr_filename = wif_filename + ".addr"

    if not os.path.exists(wif_filename):
        try:
            if not os.path.exists(os.path.dirname(wif_filename)):
                os.makedirs(os.path.dirname(wif_filename))

            privkey = pybitcointools.random_key()
            encoded = pybitcointools.encode_privkey(privkey, 'wif')
            addr = pybitcointools.privtoaddr(privkey)

            with open(wif_filename, "w") as wif_fd:
                print "writing file: {}".format(wif_filename)
                wif_fd.write(encoded)
                wif_fd.write("\n")

            with open(addr_filename, "w") as addr_fd:
                print "writing file: {}".format(addr_filename)
                addr_fd.write(addr)
                addr_fd.write("\n")
        except IOError, ioe:
            raise ClientException("IOError: {}".format(str(ioe)))


def do_load(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = BondClient(base_url=url, keyfile=key_file)

    for filename in args.filename:
        try:
            with open(filename) as fd:
                data = yaml.load(fd)
        except IOError, ioe:
            raise ClientException("IOError: {}".format(str(ioe)))

        print "Loading file: {}".format(filename)

        with UpdateBatch(client):
            for i in xrange(0, len(data['Transactions'])):
                for j in xrange(0, len(data['Transactions'][i]["Updates"])):
                    update = data['Transactions'][i]["Updates"][j]
                    if "ObjectId" not in update:
                        update["ObjectId"] = \
                            hashlib.sha256(dict2cbor(update)).hexdigest()
                    print "Sending transaction {}, {}...".format(i, j)
                    print "Update ", update
                    client.send_bond_update(update)

        if args.wait:
            client.wait_for_commit()


def do_bond(args, config):
    args.func(args, config)


def do_org(args, config):
    args.func(args, config)


def do_holding(args, config):
    args.func(args, config)


def do_user(args, config):
    args.func(args, config)


def do_order(args, config):
    args.func(args, config)


def do_quote(args, config):
    args.func(args, config)


def do_settlement(args, config):
    args.func(args, config)


def do_receipt(args, config):
    args.func(args, config)


def do_bond_list(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()

    ListWriter(state, 'bond', args.full, args.yaml).write()


def do_bond_show(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    bond_obj = try_get_then_lookup(state, 'bond',
                                   ['bond:isin', 'bond:cusip'],
                                   args.identifier)
    ShowWriter(bond_obj, 'bond', args.identifier).write()


def do_org_show(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    org_obj = try_get_then_lookup(state, 'organization',
                                  ['organization:ticker',
                                   'organization:pricing-source'],
                                  args.identifier)
    ShowWriter(org_obj, 'organization', args.identifier).write()


def do_holding_show(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    org_obj = try_get_then_lookup(state, 'holding',
                                  [],
                                  args.identifier)
    ShowWriter(org_obj, 'holding', args.identifier).write()


def do_user_show(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    user_obj = try_get_then_lookup(state, 'participant',
                                   ['participant:username',
                                    'participant:key-id'],
                                   args.identifier)
    ShowWriter(user_obj, 'User', args.identifier).write()


def do_order_show(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    order_obj = try_get_then_lookup(state, 'order', [], args.identifier)
    ShowWriter(order_obj, 'order', args.identifier).write()
    if order_obj is not None and order_obj.get('status') == 'Settled':
        settlement_obj = None
        try:
            settlement_obj = state.lookup('settlement:order-id',
                                          order_obj.get('object-id'))
            print "Settlement:"
            print "----------------------------------------------------"
        except KeyError:
            pass

        ShowWriter(settlement_obj, 'settlement',
                   order_obj.get('object-id')).write()


def do_quote_show(args, config):
    url = config.get("DEFAULT", 'url')
    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    quote_obj = try_get_then_lookup(state, 'quote', [], args.identifier)
    ShowWriter(quote_obj, 'quote', args.identifier).write()


def do_settlement_show(args, config):
    url = config.get("DEFAULT", 'url')
    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    object_id = vars(args).get('object-id')

    settlement_obj = try_get_then_lookup(state, 'settlement',
                                         ['settlement:order-id'], object_id)
    ShowWriter(settlement_obj, 'settlement', object_id).write()


def do_receipt_show(args, config):
    url = config.get("DEFAULT", 'url')
    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    receipt_obj = try_get_then_lookup(state, 'receipt', [],
                                      args.identifier)
    ShowWriter(receipt_obj, 'receipt', args.identifier).write()


def do_org_list(args, config):
    url = config.get("DEFAULT", 'url')
    key_file = config.get("DEFAULT", 'key_file')
    client = BondClient(base_url=url, keyfile=key_file)
    state = client.get_all_store_objects()

    ListWriter(state, 'organization', args.full, args.yaml).write()


def do_holding_list(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    if args.org is not None:
        org_obj = try_get_then_lookup(state, 'organization',
                                      ['organization:ticker',
                                       'organization:pricing-source'],
                                      args.org)
        if org_obj is None:
            raise ClientException("--org did not specify an organization")

        ListWriter(state, 'holding',
                   args.full, args.yaml).write('OwnerId',
                                               org_obj.get('object-id'))
    else:
        ListWriter(state, 'holding', args.full, args.yaml).write()


def do_user_list(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    ListWriter(state, 'participant', args.full, args.yaml).write()


def do_order_list(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    if args.org is not None:
        org_obj = try_get_then_lookup(state, 'organization',
                                      ['organization:ticker'], args.org)
        if org_obj is not None:
            ListWriter(state, 'order',
                       args.full, args.yaml).write('FirmId',
                                                   org_obj.get('object-id'))
        else:
            raise ClientException(
                "{} does not match an organization".format(args.org))

    elif args.user is not None:
        user_obj = try_get_then_lookup(state, 'participant',
                                       ['participant:username',
                                        'participant:key-id'], args.user)
        if user_obj is not None:
            ListWriter(state, 'order',
                       args.full, args.yaml).write('CreatorId',
                                                   user_obj.get('object-id'))
        else:
            raise ClientException("{} does not match a user".format(args.user))

    else:
        ListWriter(state, 'order', args.full, args.yaml).write()


def do_quote_list(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    if args.org is not None:
        org_obj = try_get_then_lookup(state, 'organization',
                                      ['organization:ticker',
                                       'organization:pricing-source'],
                                      args.org
                                      )
        if org_obj is not None:
            ListWriter(state, 'quote',
                       args.full,
                       args.yaml).write('Firm', org_obj.get('pricing-source'))
        else:
            raise ClientException(
                "{} does not match an organization".format(args.org))

    elif args.user is not None:
        user_obj = try_get_then_lookup(state, 'participant',
                                       ['participant:username',
                                        'participant:key-id'], args.user)
        if user_obj is not None:
            ListWriter(state, 'quote',
                       args.full, args.yaml).write('CreatorId',
                                                   user_obj.get('object-id'))
        else:
            raise ClientException("{} does not match a user".format(args.user))

    else:
        ListWriter(state, 'quote', args.full, args.yaml).write()


def do_settlement_list(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    if args.creator is not None:
        user_obj = try_get_then_lookup(state, 'participant',
                                       ['participant:username',
                                        'participant:key-id'], args.creator)
        if user_obj is not None:
            ListWriter(state, 'settlement',
                       args.full, args.yaml).write('CreatorId',
                                                   user_obj.get('object-id'))
        else:
            raise ClientException(
                "{} does not match a user".format(args.creator))
    else:
        ListWriter(state, 'settlement',
                   args.full, args.yaml).write()


def do_receipt_list(args, config):
    url = config.get("DEFAULT", 'url')

    client = BondClient(base_url=url, keyfile=None)
    state = client.get_all_store_objects()
    if args.org is not None:
        org_obj = try_get_then_lookup(state, 'organization',
                                      ['organization:ticker',
                                       'organization:pricing-source'],
                                      args.org)
        if org_obj is not None:
            ListWriter(state, 'receipt', args.full,
                       args.yaml).write('PayeeId', org_obj.get('object-id'))
        else:
            raise ClientException(
                "{} does not match an organization".format(args.org))
    elif args.bond is not None:
        bond_obj = try_get_then_lookup(state, 'bond',
                                       ['bond:isin',
                                        'bond:cusip'], args.bond)
        if bond_obj is not None:
            ListWriter(state, 'receipt', args.full,
                       args.yaml).write('BondId', bond_obj.get('object-id'))
        else:
            raise ClientException(
                "{} does not match a bond".format(args.bond))
    else:
        ListWriter(state, 'receipt', args.full, args.yaml).write()


def do_user_register(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')
    username = config.get('DEFAULT', 'username')

    client = BondClient(base_url=url, keyfile=key_file)
    client.create_participant(username, args.firm_id)
    if args.wait:
        client.wait_for_commit()


def do_user_update(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')
    key_dir = config.get("DEFAULT", 'key_dir')
    username = config.get("DEFAULT", 'username')
    args_dict = vars(args)
    print args_dict
    client = BondClient(base_url=url, keyfile=key_file)
    client.update_participant(args_dict.get("object-id"),
                              username=args.username,
                              firm_id=args.firm_id)
    # need to change the username in bond.cfg and the .wif filename
    if args.username is not None:
        change_wif_and_addr_filename(key_dir, username, args.username)
        change_config('username', args.username)
    if args.wait:
        client.wait_for_commit()


def do_org_create(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = BondClient(base_url=url, keyfile=key_file)
    client.create_org(args.name, args.object_id,
                      args.industry, args.ticker,
                      args.pricing_src, args.auth)
    if args.wait:
        client.wait_for_commit()


def do_order_create(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')
    username = config.get("DEFAULT", 'username')

    client = BondClient(base_url=url, keyfile=key_file)
    args_dict = vars(args)
    store = client.get_all_store_objects()
    limit_price = None
    if args_dict.get('order-type') == 'Limit':
        if args.limit_price is not None:
            limit_price = args.limit_price

    if args.firm_id is None:
        firm_id = args.firm_id
        try:
            firm_id = try_get_then_lookup(store, 'participant',
                                          ['participant:username'],
                                          username)["firm-id"]
            print firm_id
        except KeyError:
            pass
    else:
        firm_id = args.firm_id
    client.create_order(args.action, args_dict.get('order-type'),
                        firm_id, args.quantity,
                        args.isin, args.cusip, limit_price,
                        object_id=args.object_id)
    if args.wait:
        client.wait_for_commit()


def do_quote_create(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = BondClient(base_url=url, keyfile=key_file)
    args_dict = vars(args)

    try:
        fp = float(args_dict.get('bid-price'))
        bid_price = float_to_bondprice(fp)
    except ValueError:
        bid_price = args_dict.get('bid-price')
    try:
        fp = float(args_dict.get('ask-price'))
        ask_price = float_to_bondprice(fp)
    except ValueError:
        ask_price = args_dict.get('ask-price')

    client.create_quote(args.firm, args_dict.get('ask-qty'),
                        ask_price, args_dict.get('bid-qty'),
                        bid_price, args.isin,
                        args.cusip, args.object_id)
    if args.wait:
        client.wait_for_commit()


def do_settlement_create(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = BondClient(base_url=url, keyfile=key_file)
    args_dict = vars(args)
    client.create_settlement(args_dict.get('order-id'),
                             args.object_id)

    if args.wait:
        client.wait_for_commit()


def do_holding_create(args, config):
    url = config.get('DEFAULT', 'url')
    key_file = config.get('DEFAULT', 'key_file')

    client = BondClient(base_url=url, keyfile=key_file)
    state = client.get_all_store_objects()
    args_dict = vars(args)
    org = try_get_then_lookup(state, "organization",
                              ["organization:ticker",
                               "organization:pricing_source"], args.owner)
    if args_dict.get("asset-type") == "Currency":
        asset_id = args_dict.get("asset-id")
    else:
        asset_id = try_get_then_lookup(
            state, "bond", ["bond:cusip", "bond:isin"],
            args_dict.get("asset-id"))["object-id"]

    client.create_holding(org["object-id"],
                          args_dict.get("asset-type"),
                          asset_id, args.amount,
                          args.object_id)
    if args.wait:
        client.wait_for_commit()

from sawtooth.client import SawtoothClient

from .txn_family import RPSTransaction, RPSTransactionMessage


class RPSClient(SawtoothClient):
    def __init__(self, base_url, keyfile):
        super(RPSClient, self).__init__(
            base_url=base_url,
            store_name='RPSTransaction',
            name='RPSClient',
            keyfile=keyfile,
        )

    def create(self, name, players):
        update = {
            'Action': 'CREATE',
            'Name': name,
            'Players': players,
        }

        return self.sendtxn(RPSTransaction, RPSTransactionMessage, update)

    def shoot(self, name, hand):
        update = {
            'Action': 'SHOOT',
            'Name': name,
            'Hand': hand,
        }

        return self.sendtxn(RPSTransaction, RPSTransactionMessage, update)

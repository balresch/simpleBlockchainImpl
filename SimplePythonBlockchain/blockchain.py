import hashlib
import json
from time import time
from textwrap import dedent
from uuid import uuid4
from urllib.parse import urlparse
from flask import Flask, jsonify, request
import requests



class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []

        # nodes
        self.nodes = set()



        # create Genesis block
        self.new_block(previous_hash=1, proof=100)

    def register_node(self, address):
        '''
        Add a new node to the list of nodes

        :param address: <str> address of node, for example "http://192.168.0.5:5000"
        :return: None
        '''

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def new_block(self, proof, previous_hash=None):
        ''' Creates a new Block and adds it to the chain

        :param proof: <int> the proof given by the Proof of Work algorithm
        :param previous_hash: (Optional) <str> Hash of previous block
        :return: <dict> New block
        '''

        block = {
            "index": len(self.chain) + 1,
            "timestamp": time(),
            "transactions": self.current_transactions,
            "proof": proof,
            "previous_hash": previous_hash or self.hash(self.chain[-1]),
        }

        # reset the current list of transactions
        self.current_transactions = []

        self.chain.append(block)
        return block



    def new_transaction(self, sender, recipient, amount):
        '''
        Adds a new transaction to the list of transactions, which goes into the next mined block

        :param sender: <str> Address of the sender
        :param recipient: <str> Address of the recipient
        :param amount: <int> amount transferred
        :return: <int> The index of the block that will hold this transaction
        '''
        self.current_transactions.append({
            "sender": sender,
            "recipient": recipient,
            "amount": amount,
        })

        return self.last_block["index"] + 1

    def proof_of_work(self, last_proof):
        '''
        Simple Proof of Work Algo
        - find a number p' such that hash(pp') contains leading 4 zeroes, where p is the previous
        - p is the previous proof, p' is the new proof


        :param last_proof: <int>
        :return: <int>
        '''

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    def valid_chain(self, chain):
        '''
        Determine if a given blockchain is valid

        :param chain: <list> a blockchain
        :return: <bool> True if valid, False if not
        '''

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f"{last_block}")
            print(f"{block}")
            print("\n----------------\n")

            # check that the hash is correct
            if block["previous_hash"] != self.hash(last_block):
                return False

            # check that the pow is correct
            if not self.valid_proof(last_block["proof"], block["proof"]):
                return False

            last_block = block
            current_index =+ 1

        return True

    def resolve_conflicts(self):
        '''
        "Consensus Algorithm", resolves conflicts by replacing the chain with the longest chain available

        :return: <bool> True if replaced, False if not
        '''

        neighbours = self.nodes
        new_chain = None

        # only look for longer chains
        max_length = len(self.chain)

        # grab and verify the chains from all the nodes in our network
        for node in neighbours:
            response = requests.get(f"http://{node}/chain")

            if response.status_code == 200:
                length = response.json()["length"]
                chain = response.json()["chain"]

                # check if the chain is longer and is valid
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # replace the chain if we discovered a new one
        if new_chain:
            self.chain = new_chain
            return True

        return False
    



    @staticmethod
    def valid_proof(last_proof, proof):
        '''
        Validates the Proof: Does hash(last_proof, proof) contain 4 leading zeroes?

        :param last_proof: <int> previous proof
        :param proof: <int> current proof (to be tried)
        :return: <bool> True if correct, False of not
        '''

        guess = f"{last_proof}{proof}".encode()
        guess_hash = Blockchain._hash(guess)
        return guess_hash[:4] == "0000"

    @staticmethod
    def hash(block):
        ''' Creates a SHA3-512 hash of a block

        :param block: <dict> block
        :return: <str>
        '''

        # We must make sure that the dict is ordered, pr we'll have inconsistent hashes
        block_string = json.dumps(block, sort_keys=True).encode()

        return Blockchain._hash(block_string)

    @staticmethod
    def _hash(anything):
        '''
        helper function which implements a specific hash algo

        :param anything: any object to be hashed
        :return: <str> hash in hex
        '''

        return hashlib.sha3_512(anything).hexdigest()

    @property
    def last_block(self):
        ''' returns the last block of the chain

        '''
        return self.chain[-1]


# Instantiate our Node
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace("-", "")

# Instantiate the blockchain
blockchain = Blockchain()

@app.route("/mine", methods=["GET"])
def mine():
    # we run the PoW algo to get the next proof...
    last_block = blockchain.last_block
    last_proof = last_block["proof"]
    proof = blockchain.proof_of_work(last_proof)

    # we must receive a reward for finding the proof
    # the sender is "0" to signify that this node has mined a new coin
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    # forge the new block by adding it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        "message": "New block forged",
        "index": block["index"],
        "transactions": block["transactions"],
        "proof": block["proof"],
        "previous_hash": block["previous_hash"],
    }
    return jsonify(response), 200

@app.route("/transactions/new", methods=["POST"])
def new_transaction():

    values = request.get_json()

    # Check that the required fields are in the POST'ed data
    required = ["sender", "recipient", "amount"]

    if not all(k in values for k in required):
        return "Missing values", 400

    # Create a new Transaction
    index = blockchain.new_transaction(values["sender"], values["recipient"], values["amount"])

    response = {"message": f"Transaction will be added to block {index}"}

    return jsonify(response), 201

@app.route("/chain", methods=["GET"])
def full_chain():
    response = {
        "chain": blockchain.chain,
        "length": len(blockchain.chain)
    }
    return jsonify(response), 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
import hashlib
from time import time
import json
from uuid import uuid4
from flask import Flask, jsonify, request
from urllib.parse import urlparse
import requests
from flask_cors import CORS
class BlockChain:
    def __init__(self):
        self.nodes = set()
        self.currentTransactions = []
        self.chain = []
        # Create the genesis block
        self.newBlock(proof=100, previousHash='1')
    def registerNode(self, address):
        parseURL = urlparse(address)
        self.nodes.add(parseURL.netloc)
    def newBlock(self, proof, previousHash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.currentTransactions,
            'proof': proof,
            'previousHash': previousHash or self.hash(self.chain[-1])
        }
        self.currentTransactions = []
        self.chain.append(block)
        return block

    def newTransaction(self, sender, recipient, amount):
        self.currentTransactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        })
        return self.lastBlock['index'] + 1

    @staticmethod
    def hash(block):
        blockString = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(blockString).hexdigest()

    def proofOfWork(self, lastProof):
        proof = 0
        while self.validProof(lastProof, proof) is False:
            proof += 1
        return proof
    def validChain(self, chain):
        lastBlock = chain[0]
        currentIndex = 1
        while currentIndex < len(chain):
            block = chain[currentIndex]
            print(f'{lastBlock}')
            print(f'{block}')
            print("\n-----------\n")
            if block['previousHash'] != self.hash(lastBlock):
                return False
            if not self.validProof(lastBlock['proof'], block['proof']):
                return False
            lastBlock = block
            currentIndex += 1
        return True
    def resolveConflict(self):
        neighbors = self.nodes
        newChain = None
        maxLen = len(self.chain)
        for node in neighbors:
            try:
                response = requests.get(f'http://{node}/chain')
                if 'length' in response.json() and 'chain' in response.json():
                    length = response.json()['length']
                    chain = response.json()['chain']
                    if length > maxLen and self.validChain(chain):
                        maxLen = length
                        newChain = chain
            except requests.exceptions.RequestException as e:
                print(f'Error connecting to {node}: {e}')

        if newChain:
            self.chain = newChain
            return True
        return False


    @staticmethod
    def validProof(lastProof, proof):
        guess = f'{lastProof}{proof}'.encode()
        guessHash = hashlib.sha256(guess).hexdigest()
        return guessHash[:4] == '0000'

    @property
    def lastBlock(self):
        return self.chain[-1]


app = Flask(__name__)
CORS(app) 
nodeIdentifier = str(uuid4()).replace("-", "")
blockChain = BlockChain()


@app.route("/mine", methods=["GET"])
def mine():
    lastBlock = blockChain.lastBlock
    lastProof = lastBlock['proof']
    proof = blockChain.proofOfWork(lastProof)
    
    # Reward for finding the proof
    blockChain.newTransaction(
        sender="0",
        recipient=nodeIdentifier,
        amount=1,
    )
    
    previousHash = blockChain.hash(lastBlock)
    block = blockChain.newBlock(proof, previousHash)
    
    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previousHash': block['previousHash'],
    }
    return jsonify(response), 200


@app.route("/transactions/new", methods=["POST"])
def newTransaction():
    values = request.get_json()
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return "Missing values in request", 400
    
    index = blockChain.newTransaction(values['sender'], values['recipient'], values['amount'])
    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route("/chain", methods=["GET"])
def fullChain():
    response = {
        'chain': blockChain.chain,
        'length': len(blockChain.chain)
    }
    return jsonify(response), 200

@app.route("/nodes/register", methods=["POST"])
def selfRegister():
    value= request.get_json()
    nodes = value.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400
    for node in nodes:
        blockChain.registerNode(node)
    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockChain.nodes),
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockChain.resolveConflict()  
    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockChain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockChain.chain
        }
    return jsonify(response), 200




if __name__ == '__main__':
  app.run(host='0.0.0.0', port=3000, threaded=True)


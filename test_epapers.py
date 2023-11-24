import argparse
import sys
from DART import *
from pprint import pprint

# -----------------------------------------------------

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Run the EPapers test (test scenario A paper ICDCS).')
parser.add_argument('--build', type=str,
                    default='build/contracts/DART.json',
                    help="Path to the DART.json artifact produced by Truffle after compilation (default: build/contracts/DART.json).")
parser.add_argument('--host', type=str,
                    default='http://localhost:8545',
                    help="Hostname and port of the blockchain where DART has been deployed (default: http://localhost:8545).")
parser.add_argument('--netid', type=int,
                    default=1,
                    help="Network ID of the blockchain (default: 1).")
parser.add_argument(dest='n_eligibles', type=int, help='Number of principals to register as students and EOrg members.')
parser.add_argument(dest='n_universities', type=int, help='Number of universities to instantiate and distribute students to')

args = parser.parse_args()

nEligibles = args.n_eligibles
nUniversities = args.n_universities

## Initialize web3 by connecting it to the local Ganache provider.
w3 = Web3(Web3.HTTPProvider(args.host))
accounts = w3.eth.accounts
w3.eth.defaultAccount = accounts[0]

if len(accounts) < (3 + nEligibles + nUniversities):
    print("Not enough available Ethereum accounts! At least (N_eligibles + N_universities + 3) accounts are needed to run this test")
    sys.exit(-1)

addressesOfEligibles = accounts[3:3 + nEligibles]
addressesOfUniversities = accounts[3 + nEligibles:3 + nEligibles + nUniversities]

## Initialize the interface to interact with the DART smart contract.
DARTArtifact = json.load(open(args.build))
d = DART(DARTArtifact['abi'], DARTArtifact['networks'][str(args.netid)]['address'], w3)

# -----------------------------------------------------

# To facilitate the writing of tests and reading of results, create two pairs of dictionaries to link:

# ... principals to addresses and vice versa

PR = {
    'EPapers': accounts[0],
    'EOrg': accounts[1],
    'StateA': accounts[2]
}

for idx, addr in enumerate(addressesOfEligibles):
    PR['Principal[' + str(idx+1) + ']'] = addr

for idx, addr in enumerate(addressesOfUniversities):
    PR['Uni[' + str(idx+1) + ']'] = addr

INV_PR = {v: k for k, v in PR.items()}

print("\nPRINCIPALS:")
pprint(PR)

# ... hexadecimal rolenames to string rolenames and vice versa"

RN = {
    'canAccess': '0x000a',
    'student': '0x000b',
    'member': '0x000c',
    'university': '0x000d',
    'student': '0x000e'
}

INV_RN = {v: k for k, v in RN.items()}

print("\nROLENAMES:")
pprint(RN)

# Utility function to convert an Expression into a human-readable string
def expr2str(expr):
    if isinstance(expr, SMExpression):
        return INV_PR[expr.member]
    elif isinstance(expr, SIExpression):
        return INV_PR[expr.principal] + "." + INV_RN[expr.roleName]
    elif isinstance(expr, LIExpression):
        return INV_PR[expr.principal] + "." + INV_RN[expr.roleNameA] + "." + INV_RN[expr.roleNameB]
    elif isinstance(expr, IIExpression):
        return INV_PR[expr.principalA] + "." + INV_RN[expr.roleNameA] + " ∩ " + INV_PR[expr.principalB] + "." + INV_RN[expr.roleNameB]

# -----------------------------------------------------

# Register roles and credentials to instantiate the EPapers test policy
print("Loading policy... ", end='')

d.newRole(RN['canAccess'], {'from': PR['EPapers']})
d.newRole(RN['student'], {'from': PR['EOrg']})
d.newRole(RN['member'], {'from': PR['EOrg']})
d.newRole(RN['university'], {'from': PR['EOrg']})
d.newRole(RN['university'], {'from': PR['StateA']})

for uniAddr in addressesOfUniversities:
    d.newRole(RN['student'], {'from': uniAddr})

for idx, principalAddr in enumerate(addressesOfEligibles):
    # Register the principal as EOrg.member
    d.addSimpleMember(RN['member'], SMExpression(principalAddr), 100, {'from': PR['EOrg']})
    # Register the principal as a student of one of the universities
    d.addSimpleMember(RN['student'], SMExpression(principalAddr), 100, {'from': addressesOfUniversities[idx % len(addressesOfUniversities)]})
for uniAddr in addressesOfUniversities:
    # StateA.university ←− Uni_X
    d.addSimpleMember(RN['university'], SMExpression(uniAddr), 100, {'from': PR['StateA']})

# EOrg.university ←− StateA.university
d.addSimpleInclusion(RN['university'], SIExpression(PR['StateA'], RN['university']), 100, {'from': PR['EOrg']})
# EOrg.student ←− EOrg.university.student
d.addLinkedInclusion(RN['student'], LIExpression(PR['EOrg'], RN['university'], RN['student']), 100, {'from': PR['EOrg']})
# EPapers.canAccess ←− EOrg.member ∩ EOrg.student
d.addIntersectionInclusion(RN['canAccess'], IIExpression(PR['EOrg'], RN['student'], PR['EOrg'], RN['member']), 50, {'from': PR['EPapers']})

print("Done")

# -----------------------------------------------------

# Perform a local search for all members assigned the EPapers.canAccess role
print("\nSearching... ", end='')
solutions = d.search(SIExpression(PR['EPapers'], RN['canAccess']))
print(f"Found solutions: {len(solutions)}")

totalGas = 0
# For each found member, build the proof for the on-chain verification method based on the paths in the solutions
for idx, currSol in enumerate(solutions.values()):
    print(f'\nSolution #{idx+1}: member={INV_PR[currSol.member]}, weight={currSol.weight}')
    proofStrs = []
    proof = []
    for currEdge in currSol.path:
        if not isinstance(currEdge.toNode.expr, LIExpression):
            proofStrs.append(expr2str(currEdge.toNode.expr) + ' ←- ' + expr2str(currEdge.fromNode.expr))
            proof.append(currEdge.toNode.expr.id)
            proof.append(currEdge.fromNode.expr.id)

    # Verify the on-chain proof
    print('On-chain verification proof:')
    pprint(proofStrs)

    verifGas = d.contract.functions.verifyProof(proof, currSol.reqStackSize).estimate_gas()
    totalGas += verifGas
    verifRes = d.verifyProof(proof, currSol.reqStackSize)   
    if verifRes['principal'] != PR['EPapers'] or verifRes['rolename'] != RN['canAccess'] or verifRes['member'] != currSol.member:
        print("ERROR: invalid proof for the current solution!")
    else:
        verifRes['principal'] = INV_PR[verifRes['principal']]
        verifRes['rolename'] = INV_RN[verifRes['rolename']]
        verifRes['member'] = INV_PR[verifRes['member']]
    print(f'On-chain verification gas: {verifGas}')
    print(f'On-chain verification result: {verifRes}')

print(f"Total Students/Members: {nEligibles}\nTotal Universities: {nUniversities}\nTotal gas: {totalGas}")

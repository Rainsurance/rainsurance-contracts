from re import A
import brownie
import pytest
import time

from brownie.network.account import Account

from brownie import (
    interface,
    RainProduct,
)

from scripts.product import (
    GifProduct
)

from scripts.setup import (
    fund_riskpool,
    fund_customer,
)

from scripts.product import (
    CAPITAL_FEE_FIXED_DEFAULT,
    CAPITAL_FEE_FRACTIONAL_DEFAULT,
)

from scripts.instance import GifInstance
from scripts.util import s2b32, contractFromAddress

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


# process 5 policies in batches of 2 to confirm correct batch behavior
def test_process_policies_for_risk(
    instance: GifInstance, 
    instanceOperator, 
    gifProduct: GifProduct,
    riskpoolWallet,
    investor,
    insurer,
    customer,
):
    instanceService = instance.getInstanceService()

    product = gifProduct.getContract()
    oracle = gifProduct.getOracle().getContract()
    riskpool = gifProduct.getRiskpool().getContract()

    clOperator = gifProduct.getOracle().getClOperator()

    print('--- test setup funding riskpool --------------------------')

    token = gifProduct.getToken()
    assert token.balanceOf(riskpoolWallet) == 0

    riskpoolFunding = 200000
    fund_riskpool(
        instance, 
        instanceOperator, 
        riskpoolWallet, 
        riskpool, 
        investor, 
        token, 
        riskpoolFunding)

    # check riskpool funds and book keeping after funding
    riskpoolBalanceAfterFunding = token.balanceOf(riskpoolWallet)
    riskpoolExpectedBalance = (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT) * riskpoolFunding - CAPITAL_FEE_FIXED_DEFAULT
    assert riskpoolBalanceAfterFunding == riskpoolExpectedBalance
    assert riskpool.bundles() == 1
    assert riskpool.getCapital() == riskpoolExpectedBalance
    assert riskpool.getTotalValueLocked() == 0
    assert riskpool.getCapacity() == riskpoolExpectedBalance
    assert riskpool.getBalance() == riskpoolExpectedBalance

    # check risk bundle in riskpool and book keeping after funding
    bundleIdx = 0
    bundleAfterFunding = _getBundleDict(instance, riskpool, bundleIdx)
    bundleId = bundleAfterFunding['id']

    assert bundleAfterFunding['id'] == 1
    assert bundleAfterFunding['riskpoolId'] == riskpool.getId()
    assert bundleAfterFunding['state'] == 0
    assert bundleAfterFunding['capital'] == riskpoolExpectedBalance
    assert bundleAfterFunding['lockedCapital'] == 0
    assert bundleAfterFunding['balance'] == riskpoolExpectedBalance

    # cheeck bundle token (nft)
    bundleNftId = bundleAfterFunding['tokenId']
    bundleToken = contractFromAddress(interface.IBundleToken, instanceService.getBundleToken())
    assert bundleToken.exists(bundleNftId) == True
    assert bundleToken.burned(bundleNftId) == False
    assert bundleToken.getBundleId(bundleNftId) == bundleId
    assert bundleToken.balanceOf(investor) == 1
    assert bundleToken.ownerOf(bundleNftId) == investor

    print('--- test setup risks -------------------------------------')

    startDate = time.time() + 100
    endDate = time.time() + 1000
    placeId = [s2b32('10001.saopaulo'), s2b32('10002.paris')] # mm 
    latFloat = [-23.550620, 48.856613]
    longFloat = [-46.634370, 2.352222]
    triggerFloat = 0.1 # %
    exitFloat = 1.0 # %
    aphFloat = [5.0, 2.0] # mm

    multiplier = product.getPercentageMultiplier()
    coordMultiplier = product.getCoordinatesMultiplier()

    trigger = multiplier * triggerFloat
    exit = multiplier * exitFloat
    lat = [coordMultiplier * latFloat[0], coordMultiplier * latFloat[1]]
    long = [coordMultiplier * longFloat[0], coordMultiplier * longFloat[1]]
    aph = [aphFloat[0], aphFloat[1]]

    tx = [None, None, None, None, None]
    tx[0] = product.createRisk(startDate, endDate, placeId[0], lat[0], long[0], trigger, exit, aph[0], {'from': insurer})

    riskId = [None, None, None, None, None]
    riskId = [tx[0].return_value]
    print('riskId {}'.format(riskId))
    assert riskId[0] == product.getRiskId(placeId[0], startDate, endDate)
    

    print('--- test setup funding customers -------------------------')

    assert token.balanceOf(customer) == 0
    
    customerFunding = 5000
    fund_customer(instance, instanceOperator, customer, token, customerFunding)
    
    print('--- test create policies ---------------------------------')

    premium = [300]
    sumInsured = [2000]

    tx[0] = product.applyForPolicy(customer, premium[0], sumInsured[0], riskId[0], {'from': insurer})
    tx[1] = product.applyForPolicy(customer, premium[0], sumInsured[0], riskId[0], {'from': insurer})
    tx[2] = product.applyForPolicy(customer, premium[0], sumInsured[0], riskId[0], {'from': insurer})
    tx[3] = product.applyForPolicy(customer, premium[0], sumInsured[0], riskId[0], {'from': insurer})
    tx[4] = product.applyForPolicy(customer, premium[0], sumInsured[0], riskId[0], {'from': insurer})

    policyId = [None, None, None, None, None]
    policyId = [tx[0].return_value, tx[1].return_value, tx[2].return_value, tx[3].return_value, tx[4].return_value]
    print('policyId {}'.format(policyId))

    assert policyId[0] != policyId[1]
    assert policyId[1] != policyId[2]
    assert policyId[2] != policyId[3]
    assert policyId[3] != policyId[4]

    print('--- step trigger oracle (call chainlin node) -------------')

    tx[0] = product.triggerOracle(policyId[0], {'from': insurer})
    requestId = [tx[0].return_value] 

    # ensure event emitted as chainlink client
    assert 'OracleRequest' in tx[0].events
    assert len(tx[0].events['OracleRequest']) == 1

    # check event attributes
    clRequestEvent = tx[0].events['OracleRequest'][0]
    print('chainlink requestEvent {}'.format(clRequestEvent))
    assert clRequestEvent['requester'] == oracle.address
    assert clRequestEvent['requester'] == clRequestEvent['callbackAddr']

    # check that gif request id corresponds to expected chainlink request id
    assert 'LogRainRiskDataRequested' in tx[0].events
    assert len(tx[0].events['LogRainRiskDataRequested']) == 1

    requestEvent = tx[0].events['LogRainRiskDataRequested'][0]
    print('rain requestEvent {}'.format(requestEvent))
    assert requestEvent['requestId'] == requestId[0]
    assert requestEvent['riskId'] == riskId[0]
    assert requestEvent['placeId'] == placeId[0]
    assert requestEvent['startDate'] == startDate
    assert requestEvent['endDate'] == endDate


    print('--- step test oracle response ----------------------------')

    risk = product.getRisk(riskId[0]).dict()
    assert risk['id'] == riskId[0]
    assert risk['createdAt'] > 0
    assert risk['responseAt'] == 0
    assert risk['aaay'] == 0

    aaay = 1.0

    data = [None, None]
    data[0] = oracle.encodeFulfillParameters(
        clRequestEvent['requestId'], 
        placeId[0],
        startDate, 
        endDate, 
        aaay
    )

    # simulate callback from oracle node with call to chainlink operator contract
    tx[0] = clOperator.fulfillOracleRequest2(
        clRequestEvent['requestId'],
        clRequestEvent['payment'],
        clRequestEvent['callbackAddr'],
        clRequestEvent['callbackFunctionId'],
        clRequestEvent['cancelExpiration'],
        data[0]
    )

    print(tx[0].info())

    # focus checks on oracle 1 response
    # verify in log entry that aaay data properly arrives in rain product cotract
    assert 'LogRainRiskDataReceived' in tx[0].events
    assert len(tx[0].events['LogRainRiskDataReceived']) == 1

    receivedEvent = tx[0].events['LogRainRiskDataReceived'][0]
    print('rain requestEvent {}'.format(receivedEvent))
    assert receivedEvent['requestId'] == requestId[0]
    assert receivedEvent['riskId'] == riskId[0]
    assert receivedEvent['aaay'] == aaay

    # verify in risk that aaay data properly arrives in rain product cotract
    risk = product.getRisk(riskId[0]).dict()
    print('risk {}'.format(risk))
    assert risk['id'] == riskId[0]
    assert risk['responseAt'] > risk['createdAt']
    assert risk['aaay'] == aaay


    print('--- step test process policies (risk[0]) -----------------')

    print('balanceOf(riskpoolWallet): {}'.format(token.balanceOf(riskpoolWallet)))
    print('sumInsured[0]: {}'.format(sumInsured[0]))
    

    # claim processing for policies associated with the specified risk
    # batch size=2 triggers processing of 2 policies for this risk
    tx = product.processPoliciesForRisk(riskId[0], 2, {'from': insurer})
    processedPolicyIds = tx.return_value

    assert len(processedPolicyIds) == 2
    assert processedPolicyIds[0] == policyId[4]
    assert processedPolicyIds[1] == policyId[3]

    # process another 2 policies
    tx = product.processPoliciesForRisk(riskId[0], 2, {'from': insurer})
    processedPolicyIds = tx.return_value

    assert len(processedPolicyIds) == 2
    assert processedPolicyIds[0] == policyId[2]
    assert processedPolicyIds[1] == policyId[1]

    # another 2 policies - BUT only one remains to be actually processed
    tx = product.processPoliciesForRisk(riskId[0], 2, {'from': insurer})
    processedPolicyIds = tx.return_value

    assert len(processedPolicyIds) == 1
    assert processedPolicyIds[0] == policyId[0]

    # and finally another 2 policies - BUT none remains to be actually processed
    tx = product.processPoliciesForRisk(riskId[0], 2, {'from': insurer})
    processedPolicyIds = tx.return_value

    assert len(processedPolicyIds) == 0


def test_process_policies_mix_batch_individual_processing(
    instance: GifInstance, 
    instanceOperator, 
    gifProduct: GifProduct,
    riskpoolWallet,
    investor,
    insurer,
    customer,
):
    instanceService = instance.getInstanceService()

    product = gifProduct.getContract()
    oracle = gifProduct.getOracle().getContract()
    riskpool = gifProduct.getRiskpool().getContract()

    clOperator = gifProduct.getOracle().getClOperator()

    print('--- test setup funding riskpool --------------------------')

    token = gifProduct.getToken()

    riskpoolFunding = 200000
    fund_riskpool(
        instance, 
        instanceOperator, 
        riskpoolWallet, 
        riskpool, 
        investor, 
        token, 
        riskpoolFunding)

    # check riskpool funds and book keeping after funding
    riskpoolBalanceAfterFunding = token.balanceOf(riskpoolWallet)
    riskpoolExpectedBalance = (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT) * riskpoolFunding - CAPITAL_FEE_FIXED_DEFAULT

    # check risk bundle in riskpool and book keeping after funding
    bundleIdx = 0
    bundleAfterFunding = _getBundleDict(instance, riskpool, bundleIdx)
    bundleId = bundleAfterFunding['id']

    # cheeck bundle token (nft)
    bundleNftId = bundleAfterFunding['tokenId']
    bundleToken = contractFromAddress(interface.IBundleToken, instanceService.getBundleToken())

    print('--- test setup risks -------------------------------------')

    startDate = time.time() + 100
    endDate = time.time() + 1000
    placeId = [s2b32('10001.saopaulo'), s2b32('10002.paris')] # mm 
    latFloat = [-23.550620, 48.856613]
    longFloat = [-46.634370, 2.352222]
    triggerFloat = 0.1 # %
    exitFloat = 1.0 # %
    aphFloat = [5.0, 2.0] # mm

    multiplier = product.getPercentageMultiplier()
    coordMultiplier = product.getCoordinatesMultiplier()

    trigger = multiplier * triggerFloat
    exit = multiplier * exitFloat
    lat = [coordMultiplier * latFloat[0], coordMultiplier * latFloat[1]]
    long = [coordMultiplier * longFloat[0], coordMultiplier * longFloat[1]]
    aph = [aphFloat[0], aphFloat[1]]

    tx = [None, None, None, None, None]
    tx[0] = product.createRisk(startDate, endDate, placeId[0], lat[0], long[0], trigger, exit, aph[0], {'from': insurer})

    riskId = [None, None, None, None, None]
    riskId = [tx[0].return_value]
    print('riskId {}'.format(riskId))
    assert riskId[0] == product.getRiskId(placeId[0], startDate, endDate)
    

    print('--- test setup funding customers -------------------------')

    assert token.balanceOf(customer) == 0
    
    customerFunding = 5000
    fund_customer(instance, instanceOperator, customer, token, customerFunding)
    
    print('--- test create policies ---------------------------------')

    premium = [300]
    sumInsured = [2000]

    with brownie.reverts('ERROR:RAIN-050:NO_POLICIES'):
        product.getProcessId(customer, 0) == policyId[0]

    tx[0] = product.applyForPolicy(customer, premium[0], sumInsured[0], riskId[0], {'from': insurer})
    tx[1] = product.applyForPolicy(customer, premium[0], sumInsured[0], riskId[0], {'from': insurer})
    tx[2] = product.applyForPolicy(customer, premium[0], sumInsured[0], riskId[0], {'from': insurer})
    tx[3] = product.applyForPolicy(customer, premium[0], sumInsured[0], riskId[0], {'from': insurer})
    tx[4] = product.applyForPolicy(customer, premium[0], sumInsured[0], riskId[0], {'from': insurer})

    policyId = [None, None, None, None, None]
    policyId = [tx[0].return_value, tx[1].return_value, tx[2].return_value, tx[3].return_value, tx[4].return_value]
    print('policyId {}'.format(policyId))

    print('--- step trigger oracle (call chainlin node) -------------')

    tx[0] = product.triggerOracle(policyId[0], {'from': insurer})
    requestId = [tx[0].return_value] 

    # check event attributes
    clRequestEvent = tx[0].events['OracleRequest'][0]
    print('chainlink requestEvent {}'.format(clRequestEvent))

    requestEvent = tx[0].events['LogRainRiskDataRequested'][0]
    print('rain requestEvent {}'.format(requestEvent))

    # attempt to process policy before oracle response is in
    with brownie.reverts('ERROR:RAIN-032:ORACLE_RESPONSE_MISSING'):
        product.processPolicy(policyId[3], {'from': insurer})


    print('--- step test oracle response ----------------------------')

    risk = product.getRisk(riskId[0]).dict()

    aaay = 1.0

    data = [None, None]
    data[0] = oracle.encodeFulfillParameters(
        clRequestEvent['requestId'], 
        placeId[0],
        startDate, 
        endDate, 
        aaay
    )

    # simulate callback from oracle node with call to chainlink operator contract
    tx[0] = clOperator.fulfillOracleRequest2(
        clRequestEvent['requestId'],
        clRequestEvent['payment'],
        clRequestEvent['callbackAddr'],
        clRequestEvent['callbackFunctionId'],
        clRequestEvent['cancelExpiration'],
        data[0]
    )

    print(tx[0].info())

    receivedEvent = tx[0].events['LogRainRiskDataReceived'][0]
    print('rain requestEvent {}'.format(receivedEvent))

    # verify in risk that aaay data properly arrives in rain product cotract
    risk = product.getRisk(riskId[0]).dict()
    print('risk {}'.format(risk))


    print('--- step test process policies (risk[0]) -----------------')

    print('balanceOf(riskpoolWallet): {}'.format(token.balanceOf(riskpoolWallet)))
    print('sumInsured[0]: {}'.format(sumInsured[0]))

    assert product.policies(riskId[0]) == 5
    assert len(product.processIdsForHolder(customer)) == 5
    assert product.getProcessId(customer, 0) == policyId[0]
    assert product.getProcessId(customer, 1) == policyId[1]
    assert product.getProcessId(customer, 2) == policyId[2]
    assert product.getProcessId(customer, 3) == policyId[3]
    assert product.getProcessId(customer, 4) == policyId[4]

    assert product.processForHolder(customer, 0)['processId'] == policyId[0]
    assert product.processForHolder(customer, 1)['processId'] == policyId[1]
    assert product.processForHolder(customer, 2)['processId'] == policyId[2]
    assert product.processForHolder(customer, 3)['processId'] == policyId[3]
    assert product.processForHolder(customer, 4)['processId'] == policyId[4]

    # try to process without insurer role
    with brownie.reverts('AccessControl: account 0x5aeda56215b167893e80b4fe645ba6d5bab767de is missing role 0xf098b7742e998f92a3c749f35e64ef555edcecec4b78a00c532a4f385915955b'):
        product.processPolicy(policyId[3], {'from': customer})

    # try to process invalid processId
    with brownie.reverts('ERROR:POC-101:APPLICATION_DOES_NOT_EXIST'):
        product.processPolicy(s2b32('whateverId'), {'from': insurer})

    assert product.policies(riskId[0]) == 5

    tx = product.processPolicy(policyId[3], {'from': insurer})
    print(tx.info())
    assert 'LogRainPolicyProcessed' in tx.events
    assert tx.events['LogRainPolicyProcessed'][0]['policyId'] == policyId[3]
    assert product.policies(riskId[0]) == 4

    # claim processing for policies associated with the specified risk
    # batch size=2 triggers processing of 2 policies for this risk
    tx = product.processPoliciesForRisk(riskId[0], 2, {'from': insurer})
    processedPolicyIds = tx.return_value

    assert len(processedPolicyIds) == 2
    assert product.policies(riskId[0]) == 2
    assert processedPolicyIds[0] == policyId[4]
    assert processedPolicyIds[1] == policyId[2] # policyId[3] already processed individually 

    # process another 2 policies
    tx = product.processPoliciesForRisk(riskId[0], 2, {'from': insurer})
    processedPolicyIds = tx.return_value

    assert len(processedPolicyIds) == 2
    assert product.policies(riskId[0]) == 0
    assert processedPolicyIds[0] == policyId[1]
    assert processedPolicyIds[1] == policyId[0]


def _getBundleDict(instance, riskpool, bundleIdx):
    return _getBundle(instance, riskpool, bundleIdx).dict()


def _getBundle(instance, riskpool, bundleIdx):
    instanceService = instance.getInstanceService()
    bundleId = riskpool.getBundleId(bundleIdx)
    return instanceService.getBundle(bundleId)

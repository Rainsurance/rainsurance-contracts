import brownie
import pytest
import time

from brownie.network.account import Account

from brownie import (
    interface,
    RainProduct,
    history
)

from scripts.product import (
    GifProduct
)

from scripts.setup import (
    create_bundle,
    create_risk,
    apply_for_policy_with_bundle,
)

from scripts.instance import GifInstance
from scripts.util import s2b32, contractFromAddress

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_trigger_and_cancel_oracle_requests(
    instance: GifInstance, 
    instanceOperator, 
    gifProduct: GifProduct,
    riskpoolWallet,
    investor,
    productOwner,
    insurer,
    oracleProvider,
    riskpoolKeeper,
    customer,
    customer2
):
    instanceService = instance.getInstanceService()
    product = gifProduct.getContract()
    oracle = gifProduct.getOracle().getContract()
    clOperator = gifProduct.getOracle().getClOperator()
    riskpool = gifProduct.getRiskpool().getContract()
    token = gifProduct.getToken()

    bundleFunding = 200_000

    place = s2b32('10001.saopaulo')
    startDate = time.time() + 100
    endDate = time.time() + 2 * 24 * 3600

    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        funding=bundleFunding,
        place=place)

    riskId = create_risk(
        product,
        insurer,
        place=place,
        startDate=startDate,
        endDate=endDate)
    print('riskId {}'.format(riskId))

    premium = 300
    sumInsured = 2000
    processId = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        customer,
        product,
        bundleId,
        riskId,
        None,
        sumInsured,
        premium)
    print('processId {}'.format(processId))

    # tx = history[-1]
    # print('tx.events {}'.format(tx.events))

    # metadata = instanceService.getMetadata(processId).dict()
    # application = instanceService.getApplication(processId).dict()
    # policy = instanceService.getPolicy(processId).dict()

    # print('metadata {}'.format(metadata))
    # print('application {}'.format(application))
    # print('policy {}'.format(policy))

    print('--- step trigger oracle (call chainlink node) -------------')

    tx = product.triggerOracle(processId, "", "", {'from': insurer})
    requestId = tx.return_value
    clRequestEvent = tx.events['OracleRequest'][0]

    print('oracle request triggered'.format(tx.info()))
    assert requestId == 0

    # check if existing request can be cancelled 
    tx = product.cancelOracleRequest(processId, {'from': insurer})
    print('oracle request cancelled'.format(tx.info()))

    print('--- oracle node answers to cancelled request ----------------------------')

    risk = product.getRisk(riskId).dict()

    precActual = 1.0

    data = oracle.encodeFulfillParameters(
        clRequestEvent['requestId'], 
        place,
        startDate, 
        endDate, 
        precActual
    )

    # simulate callback from oracle node with call to chainlink operator contract
    tx = clOperator.fulfillOracleRequest2(
        clRequestEvent['requestId'],
        clRequestEvent['payment'],
        clRequestEvent['callbackAddr'],
        clRequestEvent['callbackFunctionId'],
        clRequestEvent['cancelExpiration'],
        data
    )

    success = tx.return_value
    assert success == False
    print('fulfill on cancelled request: {}'.format(tx.info()))
    print('fulfill on cancelled request. return_value: {}'.format(tx.return_value))

    print('--- oracle node triggering for 2nd time ----------------------------')

    # check if processId (risk) can now be triggered a second time
    tx = product.triggerOracle(processId, "", "", {'from': insurer})
    requestId2 = tx.return_value
    clRequestEvent2 = tx.events['OracleRequest'][0]

    print('oracle request triggered again'.format(tx.info()))
    assert requestId2 == 1

    print('--- oracle node answers to repeated request ----------------------------')

    data2 = oracle.encodeFulfillParameters(
        clRequestEvent2['requestId'],
        place,
        startDate, 
        endDate, 
        precActual
    )

    # simulate callback from oracle node with call to chainlink operator contract
    tx2 = clOperator.fulfillOracleRequest2(
        clRequestEvent2['requestId'],
        clRequestEvent2['payment'],
        clRequestEvent2['callbackAddr'],
        clRequestEvent2['callbackFunctionId'],
        clRequestEvent2['cancelExpiration'],
        data2
    )

    print('fulfill on repeated request: {}'.format(tx2.info()))
    print('fulfill on repeated request. return_value: {}'.format(tx2.return_value))

    success = tx2.return_value
    assert success == True

    risk = product.getRisk(riskId).dict()
    print('risk {}'.format(risk))
    assert risk['id'] == riskId
    assert risk['requestId'] == requestId2
    assert risk['responseAt'] > risk['createdAt']
    assert risk['precActual'] == precActual

    # check if triggering the same risk twice works
    with brownie.reverts('ERROR:RAIN-011:ORACLE_ALREADY_RESPONDED'):
        product.triggerOracle(processId, "", "", {'from': insurer})



def test_oracle_responds_with_invalid_aaay(
    instance: GifInstance, 
    instanceOperator, 
    gifProduct: GifProduct,
    riskpoolWallet,
    investor,
    productOwner,
    insurer,
    oracleProvider,
    riskpoolKeeper,
    customer,
    customer2
):
    instanceService = instance.getInstanceService()
    product = gifProduct.getContract()
    oracle = gifProduct.getOracle().getContract()
    clOperator = gifProduct.getOracle().getClOperator()
    riskpool = gifProduct.getRiskpool().getContract()
    token = gifProduct.getToken()

    bundleFunding = 200_000

    place = s2b32('10001.saopaulo')
    startDate = time.time() + 100
    endDate = time.time() + 2 * 24 * 3600

    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        funding=bundleFunding,
        place=place)

    riskId = create_risk(
        product,
        insurer,
        place=place,
        startDate=startDate,
        endDate=endDate)
    print('riskId {}'.format(riskId))

    premium = 300
    sumInsured = 2000
    processId = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        customer,
        product,
        bundleId,
        riskId,
        None,
        sumInsured,
        premium)
    print('processId {}'.format(processId))

    print('--- step trigger oracle (call chainlin node) -------------')

    risk = product.getRisk(riskId).dict()
    print('risk before triggering oracle call {}'.format(risk))
    assert risk['requestTriggered'] == False
    assert risk['requestId'] == 0
    assert risk['responseAt'] == 0

    tx = product.triggerOracle(processId, "", "", {'from': insurer})
    requestId = tx.return_value
    clRequestEvent = tx.events['OracleRequest'][0]

    print('oracle request triggered'.format(tx.info()))
    assert requestId == 0

    print('--- oracle node answers with invalid precActual ----------------------------')

    risk = product.getRisk(riskId).dict()
    print('risk after triggering oracle call before oracle callback {}'.format(risk))
    assert risk['requestTriggered'] == True
    assert risk['responseAt'] == 0

    # create oracle response with precActual value out of range
    # precActual value selected triggers a payout
    precActual = 10001

    data = oracle.encodeFulfillParameters(
        clRequestEvent['requestId'], 
        place,
        startDate, 
        endDate, 
        precActual
    )

    # simulate callback from oracle node with call to chainlink operator contract
    tx = clOperator.fulfillOracleRequest2(
        clRequestEvent['requestId'],
        clRequestEvent['payment'],
        clRequestEvent['callbackAddr'],
        clRequestEvent['callbackFunctionId'],
        clRequestEvent['cancelExpiration'],
        data
    )

    success = tx.return_value
    assert success == False

    risk = product.getRisk(riskId).dict()
    print('risk after oracle call {}'.format(risk))
    assert risk['requestTriggered'] == True
    assert risk['responseAt'] == 0

    print('--- repeat trigger/response with valid aaaay ----------------------------')

    tx = product.triggerOracle(processId, "", "", {'from': insurer})
    requestId = tx.return_value
    clRequestEvent = tx.events['OracleRequest'][0]

    print('oracle request triggered'.format(tx.info()))
    assert requestId == 1

    risk = product.getRisk(riskId).dict()
    print('risk before triggering oracle call {}'.format(risk))
    assert risk['requestTriggered'] == True
    assert risk['requestId'] == 1
    assert risk['responseAt'] == 0

    validAaay = 10.0

    validData = oracle.encodeFulfillParameters(
        clRequestEvent['requestId'], 
        place,
        startDate, 
        endDate, 
        validAaay
    )

    # simulate callback from oracle node with call to chainlink operator contract
    tx = clOperator.fulfillOracleRequest2(
        clRequestEvent['requestId'],
        clRequestEvent['payment'],
        clRequestEvent['callbackAddr'],
        clRequestEvent['callbackFunctionId'],
        clRequestEvent['cancelExpiration'],
        validData
    )

    success = tx.return_value
    assert success == True

    risk = product.getRisk(riskId).dict()
    print('risk after valid oracle callback {}'.format(risk))
    assert risk['requestTriggered'] == True
    assert risk['requestId'] == 1
    assert risk['responseAt'] > 0
    assert risk['precActual'] == validAaay

    print('--- attempt to repeat trigger once more ----------------------------')

    with brownie.reverts('ERROR:RAIN-011:ORACLE_ALREADY_RESPONDED'):
        product.triggerOracle(processId, "", "", {'from': insurer})


def test_oracle_getters(gifProduct: GifProduct):

    rainOracle = gifProduct.getOracle()
    oracle = rainOracle.getContract()

    assert oracle.getChainlinkToken() == rainOracle.chainlinkToken
    assert oracle.getChainlinkOperator() == rainOracle.chainlinkOperator
    assert oracle.getChainlinkJobId() == s2b32('1')
    assert oracle.getChainlinkPayment() == 0

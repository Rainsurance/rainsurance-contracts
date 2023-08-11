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
    ONE_DAY_DURATION,
    fund_account,
    create_bundle,
    get_bundle_dict
)

from scripts.product import (
    CAPITAL_FEE_FIXED_DEFAULT,
    CAPITAL_FEE_FRACTIONAL_DEFAULT,
    PREMIUM_FEE_FIXED_DEFAULT,
    PREMIUM_FEE_FRACTIONAL_DEFAULT,
)

from scripts.instance import GifInstance
from scripts.util import keccak256, contractFromAddress

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_happy_path(
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
    riskpool = gifProduct.getRiskpool().getContract()

    clOperator = gifProduct.getOracle().getClOperator()

    print('--- test setup funding riskpool --------------------------')

    token = gifProduct.getToken()
    assert token.balanceOf(riskpoolWallet) == 0

    tf = 10 ** token.decimals()

    startDate = time.time() + 100
    endDate = startDate + ONE_DAY_DURATION
    place = ['10001.saopaulo', '10002.paris']

    bundleFunding = 100_000
    
    create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        funding=bundleFunding,
        place=place[0])
    
    bundleFunding2 = 100_000
    
    create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        funding=bundleFunding2,
        place=place[1])


    # check riskpool funds and book keeping after funding
    riskpoolBalanceAfterFunding = token.balanceOf(riskpoolWallet)
    riskpoolExpectedBalance = (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT) * (bundleFunding + bundleFunding2) * tf - CAPITAL_FEE_FIXED_DEFAULT
    assert riskpoolBalanceAfterFunding == riskpoolExpectedBalance
    assert riskpool.bundles() == 2
    assert riskpool.getCapital() == riskpoolExpectedBalance
    assert riskpool.getTotalValueLocked() == 0
    assert riskpool.getCapacity() == riskpoolExpectedBalance
    assert riskpool.getBalance() == riskpoolExpectedBalance

    # check risk bundle in riskpool and book keeping after funding
    bundleAfterFunding = get_bundle_dict(instance, riskpool, 0)
    bundleId = bundleAfterFunding['id']

    bundleAfterFunding2 = get_bundle_dict(instance, riskpool, 1)
    bundleId2 = bundleAfterFunding2['id']

    assert bundleAfterFunding['id'] == 1
    assert bundleAfterFunding['riskpoolId'] == riskpool.getId()
    assert bundleAfterFunding['state'] == 0
    assert bundleAfterFunding['capital'] + bundleAfterFunding2['capital'] == riskpoolExpectedBalance
    assert bundleAfterFunding['lockedCapital'] == 0
    assert bundleAfterFunding['balance'] + bundleAfterFunding2['balance'] == riskpoolExpectedBalance

    # check bundle token (nft)
    bundleNftId = bundleAfterFunding['tokenId']
    bundleToken = contractFromAddress(interface.IBundleToken, instanceService.getBundleToken())
    assert bundleToken.exists(bundleNftId) == True
    assert bundleToken.burned(bundleNftId) == False
    assert bundleToken.getBundleId(bundleNftId) == bundleId
    assert bundleToken.balanceOf(investor) == 2
    assert bundleToken.ownerOf(bundleNftId) == investor

    assert bundleAfterFunding2['id'] == 2
    assert bundleAfterFunding2['riskpoolId'] == riskpool.getId()
    assert bundleAfterFunding2['state'] == 0

    # check bundle token (nft)
    bundleNftId2 = bundleAfterFunding2['tokenId']
    assert bundleToken.exists(bundleNftId2) == True
    assert bundleToken.burned(bundleNftId2) == False
    assert bundleToken.getBundleId(bundleNftId2) == bundleId2
    assert bundleToken.ownerOf(bundleNftId2) == investor


    print('--- test setup risks -------------------------------------')

    latFloat = [-23.550620, 48.856613]
    longFloat = [-46.634370, 2.352222]
    triggerFloat = 0.1 # %
    exitFloat = 1.0 # %
    aphFloat = [5.0, 2.0] # mm
    precDays = [1, 2]
    
    multiplier = product.getPercentageMultiplier()
    coordMultiplier = product.getCoordinatesMultiplier()
    precMultiplier = product.getPrecipitationMultiplier()

    trigger = multiplier * triggerFloat
    exit = multiplier * exitFloat
    lat = [coordMultiplier * latFloat[0], coordMultiplier * latFloat[1]]
    long = [coordMultiplier * longFloat[0], coordMultiplier * longFloat[1]]
    precHist = [precMultiplier * aphFloat[0], precMultiplier * aphFloat[1]]

    tx = [None, None]
    tx[0] = product.createRisk(startDate, endDate, place[0], lat[0], long[0], trigger, exit, precHist[0], precDays[0], {'from': insurer})
    tx[1] = product.createRisk(startDate, endDate, place[1], lat[1], long[1], trigger, exit, precHist[1], precDays[1], {'from': insurer})

    riskId = [None, None]
    riskId = [tx[0].return_value, tx[1].return_value]
    print('riskId {}'.format(riskId))
    assert riskId[0] != riskId[1]
    assert riskId[0] == product.getRiskId(place[0], startDate, endDate)
    assert riskId[1] == product.getRiskId(place[1], startDate, endDate)
    

    print('--- test setup funding customers -------------------------')

    assert token.balanceOf(customer) == 0
    assert token.balanceOf(customer2) == 0

    customerFunding = 500 * tf
    fund_account(instance, instanceOperator, customer, token, customerFunding)
    fund_account(instance, instanceOperator, customer2, token, customerFunding)

    # check customer funds after funding
    customerBalanceAfterFunding = token.balanceOf(customer)
    customer2BalanceAfterFunding = token.balanceOf(customer2)
    assert customerBalanceAfterFunding == customerFunding
    assert customer2BalanceAfterFunding == customerFunding


    print('--- test create policies ---------------------------------')

    premium = [300 * tf, 400 * tf]
    sumInsured = [2000 * tf, 3000 * tf]

    tx[0] = product.applyForPolicyWithBundle(customer, premium[0], sumInsured[0], riskId[0], bundleId, {'from': customer})
    tx[1] = product.applyForPolicyWithBundle(customer2, premium[1], sumInsured[1], riskId[1], bundleId2, {'from': customer2})

    print(tx[1].events)

    premiumPlusFees = [None, None]
    premiumPlusFees[0] = product.calculatePremium(premium[0])
    premiumPlusFees[1] = product.calculatePremium(premium[1])

    # check customer funds after application/paying premium
    customerBalanceAfterPremium = token.balanceOf(customer)
    customer2BalanceAfterPremium = token.balanceOf(customer2)
    assert customerBalanceAfterPremium == customerBalanceAfterFunding - premiumPlusFees[0]
    assert customer2BalanceAfterPremium == customer2BalanceAfterFunding - premiumPlusFees[1]

    # check riskpool funds after application/paying premium
    fees = [PREMIUM_FEE_FRACTIONAL_DEFAULT * premium[0] + PREMIUM_FEE_FIXED_DEFAULT, PREMIUM_FEE_FRACTIONAL_DEFAULT * premium[1] + PREMIUM_FEE_FIXED_DEFAULT]
    netPremium = [premium[0] - fees[0], premium[1] - fees[1]]
    riskpoolBalanceAfterPremiums = token.balanceOf(riskpoolWallet)
    assert riskpoolBalanceAfterPremiums == riskpoolBalanceAfterFunding + premium[0] + premium[1]

    # check risk bundle after premium
    riskpoolExpectedCapital = riskpoolExpectedBalance
    riskpoolExpectedLockedCapital = sumInsured[0] + sumInsured[1]
    riskpoolExpectedBalance += premium[0] + premium[1]

    bundleAfterPremium = get_bundle_dict(instance, riskpool, 0)
    bundleAfterPremium2 = get_bundle_dict(instance, riskpool, 1)

    assert bundleAfterPremium['id'] == 1
    assert bundleAfterPremium['riskpoolId'] == riskpool.getId()
    assert bundleAfterPremium['state'] == 0
    assert bundleAfterPremium['capital'] + bundleAfterPremium2['capital'] == riskpoolExpectedCapital
    assert bundleAfterPremium['lockedCapital'] + bundleAfterPremium2['lockedCapital'] == riskpoolExpectedLockedCapital
    assert bundleAfterPremium['balance'] + bundleAfterPremium2['balance'] == riskpoolExpectedBalance

    assert bundleAfterPremium2['id'] == 2
    assert bundleAfterPremium2['riskpoolId'] == riskpool.getId()
    assert bundleAfterPremium2['state'] == 0

    policyId = [None, None]
    policyId = [tx[0].return_value, tx[1].return_value]
    print('policyId {}'.format(policyId))
    assert policyId[0] != policyId[1]

    meta = [None, None]
    meta[0] = instanceService.getMetadata(policyId[0]).dict()
    meta[1] = instanceService.getMetadata(policyId[1]).dict()
    print('meta {}'.format(meta))

    application = [None, None]
    application[0] = instanceService.getApplication(policyId[0]).dict()
    application[1] = instanceService.getApplication(policyId[1]).dict()
    print('application {}'.format(application))

    policy = [None, None]
    policy[0] = instanceService.getPolicy(policyId[0]).dict()
    policy[1] = instanceService.getPolicy(policyId[1]).dict()
    print('policy {}'.format(policy))

    params = get_bundle_params(instanceService, riskpool, policyId[0])
    params2 = get_bundle_params(instanceService, riskpool, policyId[1])
 
    # check policy 1
    assert meta[0]['state'] == 1
    assert meta[0]['owner'] == customer
    assert meta[0]['productId'] == product.getId()
    assert application[0]['state'] == 2
    assert application[0]['premiumAmount'] >= premium[0]
    assert application[0]['sumInsuredAmount'] == sumInsured[0]
    assert params['riskId'] == riskId[0]
    assert policy[0]['state'] == 0
    assert policy[0]['premiumExpectedAmount'] == application[0]['premiumAmount']
    assert policy[0]['premiumPaidAmount'] == application[0]['premiumAmount']
 
    # check policy 2
    assert meta[1]['state'] == 1
    assert meta[1]['owner'] == customer2
    assert meta[1]['productId'] == product.getId()
    assert application[1]['state'] == 2
    assert application[1]['premiumAmount'] >= premium[1]
    assert application[1]['sumInsuredAmount'] == sumInsured[1]
    assert params2['riskId'] == riskId[1]
    assert policy[1]['state'] == 0
    assert policy[1]['premiumExpectedAmount'] == application[1]['premiumAmount']
    assert policy[1]['premiumPaidAmount'] == application[1]['premiumAmount']

    assert product.policies(riskId[0]) == 1
    assert product.policies(riskId[1]) == 1
    assert product.policies(keccak256('dummyRiskId')) == 0

    assert len(product.processIdsForHolder(customer)) == 1
    assert len(product.processIdsForHolder(customer2)) == 1

    assert product.getRiskIdForProcess(policyId[0]) == riskId[0]
    assert product.getRiskIdForProcess(policyId[1]) == riskId[1]

    assert product.getProcessId(customer, 0) == policyId[0]
    assert product.getProcessId(customer2, 0) == policyId[1] 

    assert product.getPolicyId(riskId[0], 0) == policyId[0]
    assert product.getPolicyId(riskId[1], 0) == policyId[1]

    print('--- step trigger oracle (call chainlink node) -------------')

    tx[0] = product.triggerOracle(policyId[0], "", "", {'from': insurer})
    tx[1] = product.triggerOracle(policyId[1], "", "", {'from': insurer})
    requestId = [tx[0].return_value, tx[1].return_value]

    # ensure event emitted as chainlink client
    assert 'OracleRequest' in tx[0].events
    assert len(tx[0].events['OracleRequest']) == 1

    # check event attributes
    clRequestEvent = tx[0].events['OracleRequest'][0]
    clRequestEvent1 = tx[1].events['OracleRequest'][0]
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
    assert requestEvent['placeId'] == keccak256(place[0])
    assert requestEvent['startDate'] == startDate
    assert requestEvent['endDate'] == endDate


    print('--- step test oracle response ----------------------------')

    risk = product.getRisk(riskId[0]).dict()
    assert risk['id'] == riskId[0]
    assert risk['createdAt'] > 0
    assert risk['responseAt'] == 0
    assert risk['precActual'] == 0

    # create precActual data for oracle response
    # precActual value selected triggers a payout
    precActual = precHist[0] + precMultiplier
    precActualDays = precDays[0] + 1

    data = [None, None]
    data[0] = oracle.encodeFulfillParameters(
        clRequestEvent['requestId'], 
        keccak256(place[0]),
        startDate, 
        endDate, 
        precActual,
        #precActualDays

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

    print(tx[0])

    # simulate callback for 2nd risk
    data[1] = oracle.encodeFulfillParameters(
        clRequestEvent1['requestId'],
        keccak256(place[1]), 
        startDate, 
        endDate,
        precHist[1], # setting precActual to precHist will result in a 0 payout
        #precActualDays
    )

    # simulate callback from oracle node with call to chainlink operator contract
    tx[1] = clOperator.fulfillOracleRequest2(
        clRequestEvent1['requestId'],
        clRequestEvent1['payment'],
        clRequestEvent1['callbackAddr'],
        clRequestEvent1['callbackFunctionId'],
        clRequestEvent1['cancelExpiration'],
        data[1]
    )

    # focus checks on oracle 1 response
    # verify in log entry that precActual data properly arrives in rain product cotract
    assert 'LogRainRiskDataReceived' in tx[0].events
    assert len(tx[0].events['LogRainRiskDataReceived']) == 1

    receivedEvent = tx[0].events['LogRainRiskDataReceived'][0]
    print('rain requestEvent {}'.format(receivedEvent))
    assert receivedEvent['requestId'] == requestId[0]
    assert receivedEvent['riskId'] == riskId[0]
    assert receivedEvent['precActual'] == precActual

    # verify in risk that precActual data properly arrives in rain product cotract
    risk = product.getRisk(riskId[0]).dict()
    print('risk {}'.format(risk))
    assert risk['id'] == riskId[0]
    assert risk['responseAt'] > risk['createdAt']
    assert risk['precActual'] == precActual


    print('--- step test process policies (risk[0]) -----------------')

    print('balanceOf(riskpoolWallet): {}'.format(token.balanceOf(riskpoolWallet)))
    print('sumInsured[0]: {}'.format(sumInsured[0]))
    
    assert token.balanceOf(riskpoolWallet) == riskpoolBalanceAfterPremiums
    assert riskpoolBalanceAfterPremiums >= sumInsured[0]

    # record riskpool state before processing
    balanceBeforeProcessing = riskpool.getBalance()
    valueLockedBeforeProcessing = riskpool.getTotalValueLocked()
    capacityBeforeProcessing = riskpool.getCapacity()

    with brownie.reverts('ERROR:BUC-015:BUNDLE_WITH_ACTIVE_POLICIES'):
        riskpool.closeBundle(bundleId, {'from': investor})

    with brownie.reverts('ERROR:TRS-043:PAYOUT_ALLOWANCE_TOO_SMALL'):
        tx = product.processPoliciesForRisk(riskId[0], 0, {'from': insurer})

    # create token allowance for payouts
    token.approve(
        instanceService.getTreasuryAddress(), 
        10 * bundleFunding * tf, 
        {'from': riskpoolWallet})
    
    # claim processing for policies associated with the specified risk
    # batch size=0 triggers processing of all policies for this risk    
    tx = product.processPoliciesForRisk(riskId[0], 0, {'from': insurer})
    policyIds = tx.return_value

    assert len(policyIds) == 1
    assert policyIds[0] == policyId[0]

    assert instanceService.claims(policyId[1]) == 0 # not triggered -> no claim
    assert instanceService.claims(policyId[0]) == 1 # triggered -> claim

    policy = instanceService.getPolicy(policyId[0]).dict()
    print('policy {}'.format(policy))
    assert policy['state'] == 2 # enum PolicyState {Active, Expired, Closed}
    assert policy['claimsCount'] == 1
    assert policy['openClaimsCount'] == 0
    assert policy['createdAt'] > 0
    assert policy['updatedAt'] >= policy['createdAt']

    expectedClaimPercentage = product.calculatePayoutPercentage(
        risk['trigger'],
        risk['exit'],
        risk['precHist'],
        risk['precDays'],
        risk['precActual'],
        risk['precDaysActual'],
    )

    print('multiplier {}'.format(multiplier))
    print('trigger {}'.format(risk['trigger']))
    print('exit {}'.format(risk['exit']))
    print('precHist {}'.format(risk['precHist']))
    print('precActual {}'.format(risk['precActual']))
    print('expectedClaimPercentage {}'.format(expectedClaimPercentage))

    expectedPayoutAmount = int(expectedClaimPercentage * sumInsured[0] / multiplier)

    print('expectedPayoutAmount {}'.format(expectedPayoutAmount))

    assert expectedPayoutAmount > 0
    assert expectedPayoutAmount <= sumInsured[0]

    policy = instanceService.getPolicy(policyId[0]).dict()
    print('policy {}'.format(policy))
    assert policy['state'] == 2 # enum PolicyState {Active, Expired, Closed}
    assert policy['claimsCount'] == 1
    assert policy['openClaimsCount'] == 0
    assert policy['payoutMaxAmount'] == sumInsured[0]
    assert policy['payoutAmount'] == expectedPayoutAmount
    assert policy['createdAt'] > 0
    assert policy['updatedAt'] >= policy['createdAt']

    claim = instanceService.getClaim(policyId[0], 0).dict()
    print('claim {}'.format(claim))
    assert claim['state'] == 3 # ClaimState {Applied, Confirmed, Declined, Closed}
    assert claim['claimAmount'] == expectedPayoutAmount
    assert claim['createdAt'] >= policy['createdAt']
    assert claim['updatedAt'] == claim['createdAt']

    assert instanceService.payouts(policyId[0]) == 1 

    payout = instanceService.getPayout(policyId[0], 0).dict()
    print('payout {}'.format(payout))
    assert payout['claimId'] == 0
    assert payout['state'] == 1 # PayoutState {Expected, PaidOut}
    assert payout['amount'] == expectedPayoutAmount
    assert payout['createdAt'] == claim['createdAt']
    assert payout['updatedAt'] == payout['createdAt']

    print(tx.info())

    # tests token balances for actual payout
    # riskpool wallet decrease of balance by payout amount
    assert token.balanceOf(riskpoolWallet) == riskpoolBalanceAfterPremiums - expectedPayoutAmount

    # check customer increase of balance by payout amount (and no increase for customer2)
    assert token.balanceOf(customer) == customerBalanceAfterPremium + expectedPayoutAmount 
    assert token.balanceOf(customer2) == customer2BalanceAfterPremium

    riskpoolExpectedCapital -= expectedPayoutAmount
    riskpoolExpectedLockedCapital = sumInsured[1]
    riskpoolExpectedBalance -= expectedPayoutAmount

    # check risk bundle after payout
    bundleAfterPayout = get_bundle_dict(instance, riskpool, 0)
    bundleAfterPayout2 = get_bundle_dict(instance, riskpool, 1)
    assert bundleAfterPayout['id'] == 1
    assert bundleAfterPayout['riskpoolId'] == riskpool.getId()
    assert bundleAfterPayout['state'] == 0
    assert bundleAfterPayout['capital'] + bundleAfterPayout2['capital'] == riskpoolExpectedCapital
    assert bundleAfterPayout['lockedCapital'] + bundleAfterPayout2['lockedCapital'] == riskpoolExpectedLockedCapital
    assert bundleAfterPayout['balance'] + bundleAfterPayout2['balance'] == riskpoolExpectedBalance

    # check book keeping on riskpool level
    assert riskpool.getCapital() == riskpoolExpectedCapital
    assert riskpool.getTotalValueLocked() == riskpoolExpectedLockedCapital
    assert riskpool.getBalance() == riskpoolExpectedBalance

    print('--- step test process policies (risk[1]) -----------------')

    # process 2nd policy to have all policies closed
    tx = product.processPoliciesForRisk(riskId[1], 0, {'from': insurer})
    policyIds = tx.return_value
    assert len(policyIds) == 1
    assert policyIds[0] == policyId[1]

    # high level checs
    policy = instanceService.getPolicy(policyId[1]).dict()
    assert policy['state'] == 2 # enum PolicyState {Active, Expired, Closed}
    assert policy['claimsCount'] == 1
    assert policy['openClaimsCount'] == 0

    assert instanceService.payouts(policyId[1]) == 0

    claim = instanceService.getClaim(policyId[1], 0).dict()
    print('claim {}'.format(claim))
    assert claim['state'] == 3 # ClaimState {Applied, Confirmed, Declined, Closed}
    assert claim['claimAmount'] == 0

    # check bundle state
    riskpoolExpectedLockedCapital = 0
    bundleAfter2ndPayout = get_bundle_dict(instance, riskpool, 0)
    bundleAfter2ndPayout2 = get_bundle_dict(instance, riskpool, 1)

    assert bundleAfter2ndPayout['capital'] + bundleAfter2ndPayout2['capital'] == riskpoolExpectedCapital
    assert bundleAfter2ndPayout['lockedCapital'] + bundleAfter2ndPayout2['lockedCapital'] == riskpoolExpectedLockedCapital
    assert bundleAfter2ndPayout['balance'] + bundleAfter2ndPayout2['balance'] == riskpoolExpectedBalance

    print('bundle1 After2ndPayout: {}'.format(bundleAfter2ndPayout))
    print('bundle2 After2ndPayout: {}'.format(bundleAfter2ndPayout2))

    # check riskpool state
    assert riskpool.getCapital() == riskpoolExpectedCapital
    assert riskpool.getTotalValueLocked() == riskpoolExpectedLockedCapital
    assert riskpool.getBalance() == riskpoolExpectedBalance

    print('--- step test close bundle -------------------------------')

    investorBalanceBeforeBundleClose = token.balanceOf(investor)

    riskpool.closeBundle(bundleId, {'from': investor})

    investorBalanceBeforeTokenBurn = token.balanceOf(investor)
    assert investorBalanceBeforeBundleClose == investorBalanceBeforeTokenBurn

    bundleBeforeBurn = get_bundle_dict(instance, riskpool, 0)

    assert bundleBeforeBurn['state'] == 2 # enum BundleState { Active, Locked, Closed, Burned }

    # check bundle token (nft)
    bundleNftId = bundleBeforeBurn['tokenId']
    assert bundleToken.exists(bundleNftId) == True
    assert bundleToken.burned(bundleNftId) == False
    assert bundleToken.ownerOf(bundleNftId) == investor

    tx = riskpool.burnBundle(bundleId, {'from': investor})

    # verify bundle is burned and has 0 balance
    bundleAfterBurn = get_bundle_dict(instance, riskpool, 0)

    assert bundleAfterBurn['state'] == 3 # enum BundleState { Active, Locked, Closed, Burned }
    assert bundleAfterBurn['capital'] == 0
    assert bundleAfterBurn['lockedCapital'] == 0
    assert bundleAfterBurn['balance'] == 0

    assert riskpool.getCapital() > 0
    assert riskpool.getTotalValueLocked() == 0
    assert riskpool.getBalance() > 0

    riskpool.closeBundle(bundleId2, {'from': investor})

    bundleBeforeBurn2 = get_bundle_dict(instance, riskpool, 1)

    tx = riskpool.burnBundle(bundleId2, {'from': investor})

    bundleAfterBurn2 = get_bundle_dict(instance, riskpool, 1)

    assert bundleAfterBurn2['state'] == 3 # enum BundleState { Active, Locked, Closed, Burned }
    assert bundleAfterBurn2['capital'] == 0
    assert bundleAfterBurn2['lockedCapital'] == 0
    assert bundleAfterBurn2['balance'] == 0

    assert riskpool.getCapital() == 0
    assert riskpool.getTotalValueLocked() == 0
    assert riskpool.getBalance() == 0

    # verify bundle funds are now with investor
    assert bundleToken.exists(bundleNftId) == True
    assert bundleToken.burned(bundleNftId) == True
    with brownie.reverts('ERC721: invalid token ID'):
        assert bundleToken.ownerOf(bundleNftId) == investor
    
    assert token.balanceOf(investor) == investorBalanceBeforeTokenBurn + bundleBeforeBurn['balance'] + bundleBeforeBurn2['balance']


def test_payout_percentage_calculation(gifProduct: GifProduct):

    product = gifProduct.getContract()
    multiplier = product.getPercentageMultiplier()
    precMultiplier = product.getPrecipitationMultiplier()

    # product example values
    trigger = 0.2
    exit = 1.0

    # random example values
    assert get_payout_delta(0.4, 4.20, 2, 5.88, 2, trigger, exit, product, multiplier, precMultiplier) < 0.0000001

    assert get_payout_delta(0, 4.20, 2, 5.88, 1, trigger, exit, product, multiplier, precMultiplier) < 0.0000001

    # expectedPayoutPercentage, precHist, precActual, trigger, exit, product, multiplier

    trigger = 0.05
    exit = 1.0
    precHist = 5.0
    precDays = 1
    precDaysActual = 2

    # run through product example table
    assert get_payout_delta(0, precHist, precDays, 0, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(0, precHist, precDays, 1, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(0, precHist, precDays, 2, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(0, precHist, precDays, 3, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(0, precHist, precDays, 4, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(0, precHist, precDays, 5, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(0.2, precHist, precDays, 6, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(0.4, precHist, precDays, 7, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(0.6, precHist, precDays, 8, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(0.8, precHist, precDays, 9, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(1, precHist, precDays, 10, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(1, precHist, precDays, 11, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(1, precHist, precDays, 12, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(1, precHist, precDays, 13, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(1, precHist, precDays, 14, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(1, precHist, precDays, 15, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(1, precHist, precDays, 16, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(1, precHist, precDays, 17, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(1, precHist, precDays, 18, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(1, precHist, precDays, 19, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001
    assert get_payout_delta(1, precHist, precDays, 20, precDaysActual, trigger, exit, product, multiplier, precMultiplier) < 0.0000001

def test_payout_percentage_calculation_single(gifProduct: GifProduct):

    product = gifProduct.getContract()
    multiplier = product.getPercentageMultiplier()
    precMultiplier = product.getPrecipitationMultiplier()

    trigger = 0.75
    exit = 2.0
    precHist = 2.1
    precDays = 1
    precActual = 4.2
    precDaysActual = precDays + 1
    expected_payout_percentage = 0.5 * multiplier

    payout_percentage = product.calculatePayoutPercentage(
        trigger * multiplier,
        exit * multiplier,
        precHist * precMultiplier,
        precDays,
        precActual * precMultiplier,
        precDaysActual
    )
    assert int(expected_payout_percentage + 0.5) == payout_percentage

    sumInsuredAmount = 2200
    expected_payout = int(expected_payout_percentage * sumInsuredAmount / multiplier)
    assert expected_payout == product.calculatePayout(expected_payout_percentage, sumInsuredAmount)


def get_payout_delta(
    expectedPayoutPercentage,
    precHist, precDays,
    precActual, precDaysActual,
    trigger, exit, 
    product, multiplier,
    precMultiplier
):
    calculatedPayout = product.calculatePayoutPercentage(
        trigger * multiplier,
        exit * multiplier,
        precHist * precMultiplier,
        precDays,
        precActual * precMultiplier,
        precDaysActual
    )
    print('get_payout_delta calculatedPayout: {}'.format(calculatedPayout))

    delta = abs(expectedPayoutPercentage * multiplier - calculatedPayout) / multiplier
    print('get_payout_delta delta: {}'.format(delta))

    return delta

def get_bundle_params(
    instance_service,
    riskpool,
    process_id
):
    data = instance_service.getApplication(process_id).dict()['data']
    return riskpool.decodeApplicationParameterFromData(data).dict()
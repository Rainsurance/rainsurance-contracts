import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    history,
    interface
)

from scripts.util import s2b32

from scripts.product import (
    PREMIUM_FEE_FIXED_DEFAULT,
    PREMIUM_FEE_FRACTIONAL_DEFAULT
)

from scripts.setup import (
    create_bundle, 
    create_risk,
    apply_for_policy_with_bundle,
    get_bundle_dict
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

def test_create_application(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    investor,
    customer,
    insurer,
    product,
    riskpool
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20Metadata(tokenAddress)
    tf = 10 ** token.decimals()

    place = '10001.saopaulo'

    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        place=place)

    bundleInfo = riskpool.getBundleInfo(bundleId)

    riskpoolBalanceBefore = instanceService.getBalance(riskpool.getId())
    instanceBalanceBefore = token.balanceOf(instanceWallet)

    riskId = create_risk(product, insurer, place=place)

    protectedBalance = 5000
    sumInsured = riskpool.calculateSumInsured(protectedBalance)
    premium = 500
    premiumPlusFees = product.calculatePremium(premium * tf)

    processId = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        customer,
        product,
        bundleId,
        riskId,
        None,
        protectedBalance,
        premium)

    tx = history[-1]

    print('tx.events are: {}'.format(tx.events))

    assert 'LogRainApplicationCreated' in tx.events
    assert tx.events['LogRainApplicationCreated']['processId'] == processId
    assert tx.events['LogRainApplicationCreated']['policyHolder'] == customer
    assert tx.events['LogRainApplicationCreated']['sumInsuredAmount'] == sumInsured * tf
    assert tx.events['LogRainApplicationCreated']['premiumAmount'] == premiumPlusFees

    # check collateralization with specified bundle
    appl_bundle_id = get_bundle_id(instanceService, riskpool, processId)
    assert appl_bundle_id == bundleId
    assert 'LogBundlePolicyCollateralized' in tx.events
    assert tx.events['LogBundlePolicyCollateralized']['bundleId'] == bundleId

    assert 'LogRainPolicyCreated' in tx.events
    assert tx.events['LogRainPolicyCreated']['processId'] == processId
    assert tx.events['LogRainPolicyCreated']['policyHolder'] == customer
    assert tx.events['LogRainPolicyCreated']['sumInsuredAmount'] == sumInsured * tf
    assert tx.events['LogRainPolicyCreated']['premiumAmount'] == premiumPlusFees

    metadata = instanceService.getMetadata(processId).dict()
    application = instanceService.getApplication(processId).dict()
    policy = instanceService.getPolicy(processId).dict()

    print('policy {} created'.format(processId))
    print('metadata {}'.format(metadata))
    print('application {}'.format(application))
    print('policy {}'.format(policy))

    # check metadata
    assert metadata['owner'] == customer
    assert metadata['productId'] == product.getId()

    # check application
    premiumAmount = application['premiumAmount']
    assert premiumAmount == premiumPlusFees
    assert application['sumInsuredAmount'] == sumInsured * tf

    riskpoolBalanceAfter = instanceService.getBalance(riskpool.getId())
    instanceBalanceAfter = token.balanceOf(instanceWallet)

    fixedFee = PREMIUM_FEE_FIXED_DEFAULT
    fractionalFee = PREMIUM_FEE_FRACTIONAL_DEFAULT
    premiumFees = fractionalFee * premium + fixedFee

    (
        wallet,
        protected_balance,
        applicationDuration,
        applicationBundleId,
        applicationPremium,
        applicationPlace,
        applicationRiskId
    ) = riskpool.decodeApplicationParameterFromData(application['data'])

    assert wallet == customer
    assert protected_balance == protectedBalance * tf
    assert applicationBundleId == bundleId
    assert applicationPremium == premium * tf
    assert applicationRiskId == riskId
    assert applicationPlace == place

    # check policy
    assert policy['premiumExpectedAmount'] == premiumAmount
    assert policy['premiumPaidAmount'] == premiumAmount
    assert policy['claimsCount'] == 0
    assert policy['openClaimsCount'] == 0
    assert policy['payoutMaxAmount'] == sumInsured * tf
    assert policy['payoutAmount'] == 0

    # check wallet balances against premium payment
    assert riskpoolBalanceAfter == riskpoolBalanceBefore + premium * tf
    assert instanceBalanceAfter >= instanceBalanceBefore + premiumFees * tf #TODO: replace '>' for '==' 

def test_application_with_wildcard_bundle(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    investor,
    customer,
    insurer,
    customer2,
    product,
    riskpool,
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20(tokenAddress)

    place='10001.saopaulo'
    place2 = '10002.paris'
    placeWilcard = '*'

    #bundle place = 10001.saopaulo
    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        place=place)
    
    bundleInfo = get_bundle_dict(instance, riskpool, 0)
    
    #risk place = 10002.paris
    riskId = create_risk(product, insurer, place=place2)

    protectedBalance = 5000
    maxPremium = 750

    with brownie.reverts("ERROR:RAIN-019:UNDERWRITING_FAILED"):
        apply_for_policy_with_bundle(
            instance,
            instanceOperator,
            customer,
            product,
            bundleId,
            riskId,
            None,
            protectedBalance,
            maxPremium)
    
    tx = history[-1]
    
    assert 'LogBundleMatchesApplication' in tx.events
    assert tx.events['LogBundleMatchesApplication']['errorId'] == 6

    bundleIdWildcard = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        place=placeWilcard)
    
    bundleInfo2 = get_bundle_dict(instance, riskpool, 1)
    print('bundleInfo2: {}'.format(bundleInfo2))

    apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        customer,
        product,
        bundleIdWildcard,
        riskId,
        None,
        protectedBalance,
        maxPremium)
    
    tx = history[-1]
    
    assert 'LogBundleMatchesApplication' in tx.events
    assert tx.events['LogBundleMatchesApplication']['errorId'] == 0

    #risk place = 10001.saopaulo
    riskId2 = create_risk(product, insurer, place=place)

    apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        customer,
        product,
        bundleId,
        riskId2,
        None,
        protectedBalance,
        maxPremium)
    
    tx = history[-1]
    
    assert 'LogBundleMatchesApplication' in tx.events
    assert tx.events['LogBundleMatchesApplication']['errorId'] == 0

def test_application_with_expired_bundle(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    investor,
    customer,
    insurer,
    customer2,
    product,
    riskpool,
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20(tokenAddress)

    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool)
    
    riskId = create_risk(product, insurer)

    protectedBalance = 5000
    maxPremium = 750

    processId1 = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        customer,
        product,
        bundleId,
        riskId,
        None,
        protectedBalance,
        maxPremium)

    print('application1: {}'.format(instanceService.getApplication(processId1).dict()))
    print('policy1: {}'.format(instanceService.getPolicy(processId1).dict()))

    chain.sleep(riskpool.getMaxBundleLifetime() + 1)
    chain.mine(1)

    with brownie.reverts("ERROR:RAIN-019:UNDERWRITING_FAILED"):
        apply_for_policy_with_bundle(
            instance, 
            instanceOperator,
            customer,
            product,
            bundleId,
            riskId,
            customer2,
            protectedBalance,
            maxPremium)


def get_bundle_id(
    instance_service,
    riskpool,
    process_id
):
    data = instance_service.getApplication(process_id).dict()['data']
    params = riskpool.decodeApplicationParameterFromData(data).dict()
    return params['bundleId']

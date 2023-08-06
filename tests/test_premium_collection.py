import brownie
import pytest
import time

from brownie.network import accounts
from brownie.network.account import Account

from brownie import (
    interface,
    RainProduct,
)

from scripts.product import (
    GifProduct
)

from scripts.setup import (
    fund_account,
    create_bundle,
    create_risk,
    apply_for_policy_with_bundle
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


def test_late_premium_payment(
    instance: GifInstance, 
    instanceOperator, 
    gifProduct: GifProduct,
    riskpoolWallet,
    investor,
    productOwner,
    insurer,
    riskpoolKeeper,
    customer
):
    instanceService = instance.getInstanceService()

    product = gifProduct.getContract()
    oracle = gifProduct.getOracle().getContract()
    riskpool = gifProduct.getRiskpool().getContract()
    erc20Token = gifProduct.getToken()

    tf = 10 ** erc20Token.decimals()
    
    bundleFunding = 200_000

    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        funding=bundleFunding)
    
    # check riskpool funds and book keeping after funding
    riskpoolExpectedBalance = bundleFunding * tf * (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT) - CAPITAL_FEE_FIXED_DEFAULT
    assert riskpool.getBalance() == riskpoolExpectedBalance
    assert riskpool.getBalance() == erc20Token.balanceOf(riskpoolWallet)

    riskId = create_risk(product, insurer)

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
        premium,
        transferPremium=False)
    print('processId is {}'.format(processId))

    # check riskpool funds remain unchanged as no premium has been collected
    assert riskpool.getBalance() == riskpoolExpectedBalance
    assert riskpool.getBalance() == erc20Token.balanceOf(riskpoolWallet)

    metadata = instanceService.getMetadata(processId).dict()
    application = instanceService.getApplication(processId).dict()
    policy = instanceService.getPolicy(processId).dict()

    print('metadata {}'.format(metadata))
    print('application {}'.format(application))
    print('policy {}'.format(policy))

    # check underwritten application and policy for customer
    assert metadata['owner'] == customer
    assert metadata['productId'] == product.getId()
    # enum ApplicationState {Applied, Revoked, Underwritten, Declined}
    assert application['state'] == 2
    # enum PolicyState {Active, Expired, Closed}
    assert policy['state'] == 0

    # check premium expected and paid (nothing so far)
    premiumPlusFees = product.calculatePremium(premium * tf)
    assert policy['premiumExpectedAmount'] == premiumPlusFees
    assert policy['premiumPaidAmount'] == 0

    # fund customer to pay premium now
    fund_account(instance, instanceOperator, customer, erc20Token, premiumPlusFees)
    assert erc20Token.balanceOf(customer) == premiumPlusFees
    assert erc20Token.allowance(customer, instance.getTreasury()) == premiumPlusFees

    #tx = product.collectPremium(processId, customer, premiumPlusFees, {'from': insurer})
    tx = product.collectPremium(processId, {'from': insurer})
    (success, fee, netPremium) = tx.return_value
    print('success: {}, fee: {}, netPremium: {}'.format(success, fee, netPremium))

    assert riskpool.getBalance() == riskpoolExpectedBalance + netPremium
    assert riskpool.getBalance() == erc20Token.balanceOf(riskpoolWallet)

    # check premium expected and paid (full amount)
    policy = instanceService.getPolicy(processId).dict()
    print('policy after {}'.format(policy))
    assert policy['premiumExpectedAmount'] == premiumPlusFees
    assert policy['premiumPaidAmount'] == premiumPlusFees


def test_partial_premium_payment_attempt(
    instance: GifInstance, 
    instanceOperator, 
    gifProduct: GifProduct,
    riskpoolWallet,
    investor,
    productOwner,
    insurer,
    riskpoolKeeper,
    customer
):
    instanceService = instance.getInstanceService()

    product = gifProduct.getContract()
    oracle = gifProduct.getOracle().getContract()
    riskpool = gifProduct.getRiskpool().getContract()
    erc20Token = gifProduct.getToken()

    tf = 10 ** erc20Token.decimals()
    
    bundleFunding = 200_000

    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        funding=bundleFunding)

    # check riskpool funds and book keeping after funding
    riskpoolExpectedBalance = (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT) * bundleFunding * tf - CAPITAL_FEE_FIXED_DEFAULT
    assert riskpool.getBalance() == riskpoolExpectedBalance
    assert riskpool.getBalance() == erc20Token.balanceOf(riskpoolWallet)

    # create risk
    riskId = create_risk(product, insurer)

    # create policy
    premium = 300
    sumInsured = 2000
    fund_account(instance, instanceOperator, customer, erc20Token, premium / 2)
    processId = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        customer,
        product,
        bundleId,
        riskId,
        None,
        sumInsured,
        premium,
        transferPremium=False)

    # applyForPolicy attempts to transfer the full premium amount
    # if not possible no premium is collected even if some funds would be available
    # check riskpool funds remain unchanged as no premium has been collected
    assert riskpool.getBalance() == riskpoolExpectedBalance
    assert riskpool.getBalance() == erc20Token.balanceOf(riskpoolWallet)

    # check premium expected and paid (nothing so far)
    policy = instanceService.getPolicy(processId).dict()
    assert policy['premiumExpectedAmount'] >= premium * tf
    assert policy['premiumPaidAmount'] == 0


def test_premium_payment_by_subsidies(
    instance: GifInstance, 
    instanceOperator, 
    gifProduct: GifProduct,
    riskpoolWallet,
    investor,
    productOwner,
    insurer,
    riskpoolKeeper,
    customer
):
    instanceService = instance.getInstanceService()

    product = gifProduct.getContract()
    oracle = gifProduct.getOracle().getContract()
    riskpool = gifProduct.getRiskpool().getContract()
    erc20Token = gifProduct.getToken()

    tf = 10 ** erc20Token.decimals()
    
    bundleFunding = 200_000

    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        funding=bundleFunding)

    # check riskpool funds and book keeping after funding
    riskpoolExpectedBalance = (1 - CAPITAL_FEE_FRACTIONAL_DEFAULT) * bundleFunding * tf - CAPITAL_FEE_FIXED_DEFAULT
    assert riskpool.getBalance() == riskpoolExpectedBalance
    assert riskpool.getBalance() == erc20Token.balanceOf(riskpoolWallet)

    # create risk
    riskId = create_risk(product, insurer)

    # create policy
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
        premium,
        transferPremium=False)

    # 20% premium payment by policy holder
    premiumPlusFees = product.calculatePremium(premium * tf)
    premiumPolicyHolder = premiumPlusFees / 5
    premiumSubsidies = premiumPlusFees - premiumPolicyHolder

    fund_account(instance, instanceOperator, customer, erc20Token, premiumPolicyHolder)
    assert erc20Token.balanceOf(customer) == premiumPolicyHolder

    tx = product.collectPremium(processId, customer, premiumPolicyHolder, {'from': insurer})
    (success, fee, netPremium) = tx.return_value

    assert success
    assert fee + netPremium == premiumPolicyHolder
    assert erc20Token.balanceOf(customer) == 0

    policy = instanceService.getPolicy(processId).dict()
    
    assert policy['premiumExpectedAmount'] == premiumPlusFees
    assert policy['premiumPaidAmount'] == premiumPolicyHolder

    # 80% premium subidies payment
    donor = accounts.add()
    accounts[9].transfer(donor, 100000000)
    erc20Token.transfer(donor, premiumSubsidies, {'from': instanceOperator})
    erc20Token.approve(product, premiumSubsidies, {'from': donor})

    assert erc20Token.balanceOf(donor) == premiumSubsidies
    riskpoolBeforeDonation = erc20Token.balanceOf(riskpoolWallet)

    # collect premium from 1st ransfers amount from donor to customer then performs
    # standard premium collection. therefore, customer needs to have sufficient allowance
    erc20Token.approve(instance.getTreasury(), premiumSubsidies, {'from': customer})
    tx = product.collectPremium(processId, donor, premiumSubsidies, {'from': insurer})
    (success, fee, netPremium) = tx.return_value

    assert success
    assert fee + netPremium == premiumSubsidies
    assert erc20Token.balanceOf(donor) == 0
    assert erc20Token.balanceOf(riskpoolWallet) == riskpoolBeforeDonation + netPremium

    policy = instanceService.getPolicy(processId).dict()
    assert policy['premiumExpectedAmount'] == premiumPlusFees
    assert policy['premiumPaidAmount'] == premiumPlusFees


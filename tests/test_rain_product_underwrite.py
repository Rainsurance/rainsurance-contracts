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

from scripts.instance import GifInstance
from scripts.util import s2b32, contractFromAddress

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


# underwrite the policy after the apply_for_policy has failed due to low riskpool balance
def test_underwrite_after_apply_with_riskpool_empty(
    instance: GifInstance, 
    instanceOperator, 
    gifProduct: GifProduct,
    riskpoolWallet,
    riskpoolKeeper: Account,    
    investor,
    insurer,
    customer,
):
    instanceService = instance.getInstanceService()

    product = gifProduct.getContract()
    oracle = gifProduct.getOracle().getContract()
    riskpool = gifProduct.getRiskpool().getContract()

    clOperator = gifProduct.getOracle().getClOperator()

    print('--- test setup underfunded riskpool --------------------------')

    token = gifProduct.getToken()
    assert token.balanceOf(riskpoolWallet) == 0

    riskpoolBalanceBeforeFunding = token.balanceOf(riskpoolWallet)
    assert 0 == riskpoolBalanceBeforeFunding
    
    riskId = prepare_risk(product, insurer)

    premium = 300
    sumInsured = 2000

    # ensure the riskpool is funded, but too low for insurance
    riskpoolFunding = 1000
    fund_riskpool(
        instance, 
        instanceOperator, 
        riskpoolWallet, 
        riskpool, 
        investor, 
        token, 
        riskpoolFunding)
    riskpoolBalanceAfterFunding = token.balanceOf(riskpoolWallet)
    assert riskpoolBalanceAfterFunding > 0

    print('--- test setup customer --------------------------')

    customerFunding = 5000
    fund_customer(instance, instanceOperator, customer, token, customerFunding)

    print('--- apply for policy on underfunded riskpool --------------------------')
    # ensure application works for policy with underfunded riskpool
    tx = product.applyForPolicy(customer, premium, sumInsured, riskId, {'from': insurer})
    process_id = tx.return_value
    events = tx.events
    print(events)

    assert 'LogRainPolicyApplicationCreated' in events
    assert 'LogRiskpoolCollateralizationFailed' in events

    assert 'LogRainPolicyCreated' not in events
    
    # ensure application exists and has state Applied
    application = instanceService.getApplication(process_id)
    assert 0 == application[0] # ApplicationState.Applied

    assert 1 == product.applications()
    assert 0 == product.policies(riskId)

    assert process_id == product.getApplicationId(0)

    # ensure that explicity underwriting still fails
    tx = product.underwrite(process_id, {'from': insurer})
    assert False == tx.return_value
    
    events = tx.events
    print(events)
    assert 'LogRiskpoolCollateralizationFailed' in events

    print('--- fully fund riskpool --------------------------')
    # ensure the riskpool is fully funded
    riskpool.setMaximumNumberOfActiveBundles(2, {'from': riskpoolKeeper})
    riskpoolFunding = 20000
    fund_riskpool(
        instance, 
        instanceOperator, 
        riskpoolWallet, 
        riskpool, 
        investor, 
        token, 
        riskpoolFunding)

    # check riskpool funds and book keeping after funding
    riskpoolBalanceAfter2ndFunding = token.balanceOf(riskpoolWallet)
    assert riskpoolBalanceAfter2ndFunding > riskpoolBalanceAfterFunding
    assert riskpool.bundles() == 2
    
    print('--- underwrite application --------------------------')
    # now underwrite the policy as the riskpool is now funded
    tx = product.underwrite(process_id, {'from': insurer})
    assert True == tx.return_value

    events = tx.events
    print(events)
    assert 'LogRainPolicyCreated' in events

    # ensure application exists and has state Applied
    application = instanceService.getApplication(process_id)
    assert 2 == application[0] # ApplicationState.Underwritten

def test_underwrite_invalid_policy_id(
    gifProduct: GifProduct,
    insurer,
):
    product = gifProduct.getContract()

    with brownie.reverts("ERROR:POC-101:APPLICATION_DOES_NOT_EXIST"):
        tx = product.underwrite(s2b32('does_not_exist'), {'from': insurer})



def prepare_risk(product, insurer):
    print('--- test setup risks -------------------------------------')

    startDate = time.time() + 100
    endDate = time.time() + 1000
    placeId = s2b32('10001.saopaulo') # mm 
    latFloat = -23.550620
    longFloat = -46.634370
    triggerFloat = 0.1 # %
    exitFloat = 1.0 # %
    precHistFloat = 1.0 # mm
    precDays = 2
    
    multiplier = product.getPercentageMultiplier()
    coordMultiplier = product.getCoordinatesMultiplier()
    precMultiplier = product.getPrecipitationMultiplier()
    
    lat = latFloat * coordMultiplier
    long = longFloat * coordMultiplier
    trigger = multiplier * triggerFloat
    exit = multiplier * exitFloat
    precHist = precMultiplier * precHistFloat

    tx = product.createRisk(startDate, endDate, placeId, lat, long, trigger, exit, precHist, precDays, {'from': insurer})
    return tx.return_value
